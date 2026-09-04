"""
Pruebas de la Fase 2.

Lo que aquí se congela no son detalles de implementación sino las propiedades de
las que depende que el sistema no mienta: que el intervalo cubra lo que promete,
que la partición no filtre vecinos, que el segmento de Mondrian se pueda calcular
sin conocer la respuesta, y que los bugs que ya costaron encontrar no vuelvan.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas.config import cargar
from atlas.modelos import apilado, conforme, datos, evaluacion, hedonico

CFG = cargar()
ALPHA = 0.05


# ------------------------------------------------------------------ conforme
def test_el_intervalo_conforme_cubre_lo_que_promete():
    """
    La propiedad que justifica todo el módulo: con datos intercambiables, la
    cobertura en prueba debe alcanzar (1−α). Se repite sobre muchas semillas
    porque una sola corrida no distingue una garantía de una casualidad.
    """
    coberturas = []
    for s in range(40):
        rng = np.random.default_rng(s)
        n = 600
        y = rng.normal(0, 1, n)
        # Cuantiles deliberadamente MAL calibrados: demasiado estrechos. Si el
        # conformal sirve, los arregla; si no, esta prueba lo desnuda.
        lo, hi = np.full(n, -0.4), np.full(n, 0.4)
        cal = slice(0, 300)
        c = conforme.calibrar(y[cal], lo[cal], hi[cal], ALPHA)
        blo, bhi = conforme.aplicar(lo[300:], hi[300:], c)
        coberturas.append(np.mean((y[300:] >= blo) & (y[300:] <= bhi)))

    media = float(np.mean(coberturas))
    assert media >= 1 - ALPHA - 0.01, f"cobertura media {media:.3f}, prometía {1 - ALPHA}"

    # Y sin conformalizar, esa misma banda [−0.4, 0.4] sobre una normal estándar
    # cubre ~31%. El contraste es lo que hace que la corrección no sea
    # decorativa: no está afinando un intervalo casi bueno, está arreglando uno
    # que cubría un tercio de lo que prometía.
    crudo = np.random.default_rng(0).normal(0, 1, 20000)
    assert np.mean((crudo >= -0.4) & (crudo <= 0.4)) < 0.4


def test_sin_suficientes_datos_no_finge_una_garantia():
    """
    Con n < 1/α − 1 el índice ⌈(n+1)(1−α)⌉ cae fuera de la muestra: no existe
    corrección finita. Debe devolver infinito —intervalo no informativo— y no
    un número plausible que aparentaría una garantía inexistente.
    """
    assert conforme._cuantil_conforme(np.arange(5.0), 0.05) == float("inf")
    assert np.isfinite(conforme._cuantil_conforme(np.arange(200.0), 0.05))


def test_el_cuantil_conforme_usa_n_mas_1_y_no_el_percentil_ingenuo():
    """
    El ⌈(n+1)(1−α)⌉ es lo que da la garantía en muestra finita. El percentil
    ingenuo queda por debajo, y siempre en la dirección de cubrir de MENOS.
    """
    E = np.arange(100.0)
    conf = conforme._cuantil_conforme(E, 0.05)
    ingenuo = float(np.percentile(E, 95))
    assert conf >= ingenuo


def test_mondrian_arregla_un_segmento_que_el_global_dejaba_corto():
    """
    El caso de uso entero de Mondrian: un grupo mucho más disperso que el resto.
    Con una sola corrección global ese grupo queda descubierto aunque el
    promedio se vea bien; calibrando por grupo, se cubre.
    """
    rng = np.random.default_rng(7)
    n = 1200
    grupo = np.where(np.arange(n) % 6 == 0, "volatil", "tranquilo")
    y = np.where(grupo == "volatil", rng.normal(0, 4, n), rng.normal(0, 1, n))
    lo, hi = np.full(n, -1.0), np.full(n, 1.0)

    cal, pru = slice(0, 600), slice(600, n)
    g = pd.Series(grupo)

    solo_global = conforme.calibrar(y[cal], lo[cal], hi[cal], ALPHA)
    con_grupos = conforme.calibrar(y[cal], lo[cal], hi[cal], ALPHA, grupos_cal=g[cal])

    def cobertura(c, grupos):
        blo, bhi = conforme.aplicar(lo[pru], hi[pru], c, grupos)
        dentro = (y[pru] >= blo) & (y[pru] <= bhi)
        return float(dentro[(g[pru] == "volatil").to_numpy()].mean())

    assert cobertura(solo_global, None) < 1 - ALPHA, \
        "el global debería quedarse corto en el segmento volátil"
    assert cobertura(con_grupos, g[pru]) >= 1 - ALPHA - 0.03


def test_la_segmentacion_se_adapta_al_tamano_de_la_calibracion():
    """
    El bug que congela: con 290 inmuebles de calibración, `tipo × tercil` daba
    nueve grupos y ocho quedaban por debajo del mínimo, así que Mondrian no
    hacía nada mientras el informe parecía segmentado. Ahora se baja a una
    segmentación que la muestra sí sostiene.
    """
    rng = np.random.default_rng(3)
    tipo_pocos = pd.Series(rng.choice(["depto", "casa", "terreno"], 200))
    nombre, seg, _ = conforme.elegir_segmentacion(
        tipo_pocos, pd.Series(rng.lognormal(10, 0.5, 200)), ALPHA)
    assert seg.nunique() <= 3, "con 200 filas no se sostienen nueve grupos"

    tipo_muchos = pd.Series(rng.choice(["depto", "casa"], 4000))
    nombre_g, seg_g, cortes = conforme.elegir_segmentacion(
        tipo_muchos, pd.Series(rng.lognormal(10, 0.5, 4000)), ALPHA)
    assert seg_g.nunique() >= seg.nunique(), "con más datos debe poder afinar más"
    assert nombre_g == "tipo × tercil" and cortes is not None


def test_el_segmento_se_calcula_sin_conocer_la_respuesta():
    """
    El segmento de Mondrian tiene que salir de la PREDICCIÓN, porque al valuar
    un inmueble el precio real es justamente lo que no se sabe. `segmentar`
    debe poder aplicarse a datos nuevos usando sólo los cortes aprendidos.
    """
    tipo = pd.Series(["depto"] * 300 + ["casa"] * 300)
    pred = pd.Series(np.linspace(1000, 9000, 600))
    nombre, _, cortes = conforme.elegir_segmentacion(tipo, pred, ALPHA)

    nuevos = conforme.segmentar(nombre, pd.Series(["depto", "casa"]),
                                pd.Series([1100.0, 8800.0]), cortes)
    assert len(nuevos) == 2 and nuevos.notna().all()
    # Los mismos cortes aplicados dos veces dan lo mismo: si cada conjunto usara
    # sus propios terciles, "caro" significaría cosas distintas en cada uno.
    otra = conforme.segmentar(nombre, pd.Series(["depto", "casa"]),
                              pd.Series([1100.0, 8800.0]), cortes)
    assert list(nuevos) == list(otra)


def test_el_intervalo_nunca_sale_invertido():
    c = conforme.Conformal(alpha=0.05, global_=-5.0)   # corrección enorme y negativa
    lo, hi = conforme.aplicar(np.array([1.0, 2.0]), np.array([1.5, 2.5]), c)
    assert (lo <= hi).all()


# ------------------------------------------------------------------- apilado
def test_el_apilado_pesa_mas_al_modelo_que_acierta():
    rng = np.random.default_rng(11)
    y = rng.normal(0, 1, 500)
    bueno = y + rng.normal(0, 0.1, 500)
    malo = rng.normal(0, 1, 500)
    a = apilado.ajustar({"bueno": bueno, "malo": malo}, y)
    assert a.pesos[a.nombres.index("bueno")] > a.pesos[a.nombres.index("malo")]
    assert np.isclose(a.pesos.sum(), 1.0)
    assert (a.pesos >= 0).all(), "los pesos negativos harían ininterpretable la mezcla"


# ---------------------------------------------------------------- evaluación
def test_la_cobertura_medida_es_la_fraccion_dentro_del_intervalo():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    lo = np.array([0.0, 0.0, 0.0, 0.0])
    hi = np.array([1.5, 2.5, 2.5, 2.5])       # cubre 2 de 4
    r = evaluacion.intervalo(y, lo, hi, 0.05)
    assert r.cobertura == 0.5
    assert not r.cumple()


def test_el_error_se_reporta_en_pesos_no_en_logaritmos():
    """Un R² sobre logaritmos no le dice nada a nadie; un 10% de error sí."""
    y = np.log(np.array([1000.0, 2000.0, 4000.0]))
    pred = np.log(np.array([1100.0, 1800.0, 4400.0]))   # +10%, −10%, +10%
    m = evaluacion.punto(y, pred)
    assert abs(m.mdape_pct - 10.0) < 0.01
    assert m.dentro_20_pct == 100.0


# -------------------------------------------------------------------- diseño
def test_se_quitan_las_columnas_linealmente_dependientes():
    """
    El bug que congela: `tipo_otro` se quitaba por nombre como categoría de
    referencia, y cuando esa categoría no existía en los datos no se quitaba
    ninguna. Las indicadoras sumaban 1 contra la constante y statsmodels
    devolvía coeficientes indeterminados con un SingularMatrixWarning.
    """
    rng = np.random.default_rng(5)
    a = rng.normal(size=200)
    b = rng.normal(size=200)
    Z = np.column_stack([a, b, a + b])          # la tercera es redundante
    Zr, nombres, fuera = hedonico._rango_completo(Z, ["a", "b", "a+b"])
    assert Zr.shape[1] == 2
    assert len(fuera) == 1 and len(nombres) == 2


# ------------------------------------------------------------------ partición
def test_ningun_bloque_cae_en_dos_conjuntos():
    """
    La fuga que la partición existe para evitar: si un bloque estuviera en
    entrenamiento y en prueba, un comparable vecino se vería a los dos lados y
    el desempeño saldría inflado.
    """
    rng = np.random.default_rng(2)
    bloque = pd.Series(rng.choice([f"b{i}" for i in range(40)], 2000))
    p = datos.particion(bloque, CFG)

    conjuntos = {k: set(bloque[v]) for k, v in p.items()}
    assert not (conjuntos["entrena"] & conjuntos["calibra"])
    assert not (conjuntos["entrena"] & conjuntos["prueba"])
    assert not (conjuntos["calibra"] & conjuntos["prueba"])
    assert sum(v.sum() for v in p.values()) == len(bloque), "nadie puede quedarse fuera"


def test_la_particion_es_determinista():
    bloque = pd.Series([f"b{i % 30}" for i in range(1500)])
    a = datos.particion(bloque, CFG)
    b = datos.particion(bloque, CFG)
    for k in a:
        assert (a[k] == b[k]).all()


def test_con_muy_pocos_bloques_avisa_en_vez_de_partir_mal():
    """Dos bloques no se pueden partir en tres sin dejar uno vacío."""
    with pytest.raises(ValueError, match="pocos bloques"):
        datos.particion(pd.Series(["a"] * 50 + ["b"] * 50), CFG)


def test_las_fracciones_quedan_cerca_de_lo_pedido():
    rng = np.random.default_rng(4)
    bloque = pd.Series(rng.choice([f"b{i}" for i in range(60)], 3000))
    p = datos.particion(bloque, CFG, fracciones=(0.6, 0.2, 0.2))
    n = len(bloque)
    assert abs(p["entrena"].sum() / n - 0.6) < 0.12
    assert abs(p["prueba"].sum() / n - 0.2) < 0.12


# ------------------------------------ los bugs que destapó la primera corrida real
def test_los_grupos_chicos_se_agrupan_y_se_calibran_juntos():
    """
    El bug que congela, encontrado sobre datos reales de la CDMX: el segmento
    `depto·barato` tenía 12 inmuebles en calibración, quedó sin calibrar, cayó a
    la corrección global —dominada por los grupos numerosos— y cubrió **69.6%**
    cuando prometía 95%. Ahora los chicos se juntan en un cubo que sí tiene
    observaciones suficientes para una corrección válida sobre su unión.
    """
    rng = np.random.default_rng(21)
    n = 1500
    # Un grupo grande y tranquilo, y tres chiquitos y dispersos. Los chicos
    # tienen que quedar POR DEBAJO del mínimo en calibración (~13 cada uno con
    # 750 filas), que es justo el caso en el que la primera versión fallaba.
    g = rng.choice(["grande", "chico_a", "chico_b", "chico_c"], n,
                   p=[0.85, 0.05, 0.05, 0.05])
    y = np.where(g == "grande", rng.normal(0, 1, n), rng.normal(0, 5, n))
    lo, hi = np.full(n, -1.0), np.full(n, 1.0)
    cal, pru = slice(0, 750), slice(750, n)
    gs = pd.Series(g)

    c = conforme.calibrar(y[cal], lo[cal], hi[cal], ALPHA, grupos_cal=gs[cal])
    assert c.grupos_en_pool, "los chicos deberían haberse agrupado"
    assert not c.grupos_sin_calibrar, "agrupados, ya no deben quedar sin calibrar"
    # Todos los chicos comparten la MISMA corrección: la de su unión.
    assert len({c.por_grupo[x] for x in c.grupos_en_pool}) == 1

    blo, bhi = conforme.aplicar(lo[pru], hi[pru], c, gs[pru])
    dentro = (y[pru] >= blo) & (y[pru] <= bhi)
    chicos = gs[pru].str.startswith("chico_").to_numpy()
    assert dentro[chicos].mean() >= 1 - ALPHA - 0.03, \
        "el cubo de chicos debe cubrir lo prometido sobre su unión"


def test_la_categoria_de_referencia_no_se_confunde_con_otro():
    """
    El bug que congela: la fila sin ninguna indicadora encendida es la categoría
    de REFERENCIA —la que se dejó fuera del diseño—, no "otro". En los datos
    reales la referencia resultó ser `casa`, y las 144 casas de la calibración
    aparecían en el informe como "otro" mientras el segmento `casa` no existía.
    Se detectó porque la salida traía depto, otro y terreno y ninguna casa, que
    en un inventario inmobiliario es imposible.
    """
    from pipelines import fase2

    X = pd.DataFrame({
        "tipo_depto": [1.0, 0.0, 0.0, 0.0],
        "tipo_terreno": [0.0, 1.0, 0.0, 0.0],
        "otra_variable": [1.0, 2.0, 3.0, 4.0],
    })
    d = datos.Datos(
        X=X, y=pd.Series([1.0] * 4), bloque=pd.Series(["b"] * 4),
        superficie=pd.Series([50.0] * 4), coords=np.zeros((4, 2)),
        operacion="venta", tipo_referencia="casa",
    )
    t = fase2._tipo_de(d, np.array([True] * 4))
    assert list(t) == ["depto", "terreno", "casa", "casa"]
    assert "otro" not in set(t), "la referencia era casa, no otro"


def test_el_vif_quita_la_colinealidad_que_el_rango_deja_pasar():
    """
    El QR pivotante sólo ve dependencias EXACTAS. La colinealidad real es
    casi-exacta y pasa entera: con ella el hedónico daba R²=0.456 dentro de
    muestra y R²=0.002 fuera, con dos variables gemelas cargando coeficientes
    enormes de signo opuesto que se cancelaban.
    """
    rng = np.random.default_rng(13)
    a = rng.normal(size=400)
    gemela = a + rng.normal(0, 0.01, 400)      # correlación ~0.9999, no exacta
    libre = rng.normal(size=400)
    Z = np.column_stack([a, gemela, libre])
    nombres = ["a", "gemela", "libre"]

    _, _, fuera_rango = hedonico._rango_completo(Z, nombres)
    assert fuera_rango == [], "el filtro de rango no ve la colinealidad casi-exacta"

    Zp, quedan, fuera_vif = hedonico.podar_por_vif(Z, nombres)
    assert len(fuera_vif) == 1 and Zp.shape[1] == 2
    assert "libre" in quedan, "la variable independiente no se toca"


def test_el_conformal_normalizado_cubre_y_adapta_el_ancho():
    """
    El intervalo normalizado tiene que hacer dos cosas: cubrir lo prometido, y
    ser MÁS ANCHO donde el modelo falla más. Si sólo cubriera, un intervalo de
    ancho constante bastaría y no habría razón para modelar la dispersión.
    """
    rng = np.random.default_rng(31)
    n = 2000
    # La mitad fácil (poco ruido) y la mitad difícil (mucho): σ̂ debe notarlo.
    dificil = np.arange(n) % 2 == 0
    y = np.where(dificil, rng.normal(0, 3, n), rng.normal(0, 0.5, n))
    pred = np.zeros(n)
    sigma = np.where(dificil, 3.0, 0.5)          # una σ̂ perfecta, para aislar la lógica

    cal, pru = slice(0, 1000), slice(1000, n)
    c = conforme.calibrar_normalizado(y[cal], pred[cal], sigma[cal], ALPHA)
    lo, hi = conforme.aplicar_normalizado(pred[pru], sigma[pru], c)

    dentro = (y[pru] >= lo) & (y[pru] <= hi)
    assert dentro.mean() >= 1 - ALPHA - 0.02

    ancho = hi - lo
    d = dificil[pru]
    assert np.median(ancho[d]) > 3 * np.median(ancho[~d]), \
        "el intervalo debe abrirse donde el modelo sabe menos"


def test_bajar_el_nivel_de_confianza_estrecha_el_intervalo():
    """
    Con el score normalizado, cambiar α es otro cuantil de los mismos scores:
    no hay que reentrenar nada. Y menos confianza tiene que dar menos ancho.
    """
    rng = np.random.default_rng(33)
    n = 1200
    y = rng.normal(0, 1, n)
    pred, sigma = np.zeros(n), np.ones(n)
    cal, pru = slice(0, 600), slice(600, n)

    anchos = []
    for a in (0.5, 0.2, 0.05):
        c = conforme.calibrar_normalizado(y[cal], pred[cal], sigma[cal], a)
        lo, hi = conforme.aplicar_normalizado(pred[pru], sigma[pru], c)
        anchos.append(float(np.median(hi - lo)))
    assert anchos[0] < anchos[1] < anchos[2]


def test_la_dispersion_se_ajusta_fuera_de_muestra():
    """
    σ̂ ajustado sobre residuales de ENTRENAMIENTO aprendería que el sistema es
    más preciso de lo que es, y el intervalo saldría estrecho y falso. La firma
    obliga a pasar predicciones fuera de muestra.
    """
    import inspect

    from atlas.modelos import arboles
    assert "pred_fuera" in inspect.signature(arboles.dispersion).parameters
    rng = np.random.default_rng(37)
    X = pd.DataFrame({"a": rng.normal(size=300), "b": rng.normal(size=300)})
    y = pd.Series(rng.normal(size=300))
    s = arboles.dispersion(X, y, y.to_numpy() + rng.normal(0, 1, 300), semilla=0)
    assert (s.predict(X) > 0).all(), "una dispersión negativa no significa nada"


def test_el_estabilizador_estrecha_el_intervalo_cuando_sigma_es_ruidosa():
    """
    El bug que congela, medido en simulación: con la MISMA cobertura, una σ̂
    ruidosa infla la corrección conforme de 1.92 a 3.44 y casi DUPLICA el ancho.
    El mecanismo es que el score |y−ŷ|/σ̂ tiene colas gruesas donde σ̂ se queda
    corta, y unos pocos puntos así arrastran el cuantil, que luego se le aplica
    a todo el mundo.

    Se vio en producción: al pasar de 56 a 137 variables el error puntual mejoró
    (mediana 24.7% → 22.0%) y el intervalo se ENSANCHÓ (±107% → ±126%).
    """
    rng = np.random.default_rng(41)
    n = 2000
    sig_real = np.exp(rng.normal(0, 0.5, n))
    y = rng.normal(0, 1, n) * sig_real
    pred = np.zeros(n)
    # σ̂ ruidosa: acierta la forma pero con error multiplicativo grande.
    sigma_ruidosa = sig_real * np.exp(rng.normal(0, 0.8, n))
    escala = float(np.median(np.abs(y)))

    def ancho_y_cobertura(gamma):
        s = sigma_ruidosa + gamma * escala
        cal, pru = slice(0, 1000), slice(1000, n)
        c = conforme.calibrar_normalizado(y[cal], pred[cal], s[cal], ALPHA)
        lo, hi = conforme.aplicar_normalizado(pred[pru], s[pru], c)
        dentro = (y[pru] >= lo) & (y[pru] <= hi)
        return float(np.median(hi - lo)), float(dentro.mean())

    ancho0, cob0 = ancho_y_cobertura(0.0)
    ancho1, cob1 = ancho_y_cobertura(1.0)
    assert ancho1 < ancho0, "estabilizar debe estrechar cuando σ̂ es ruidosa"
    # Y sin perder cobertura: la garantía no depende de σ̂, así que estabilizar
    # compra estrechez sin pagar validez.
    assert cob1 >= 1 - ALPHA - 0.03 and cob0 >= 1 - ALPHA - 0.03


def test_todos_los_gammas_dan_intervalos_validos():
    """
    Es la razón por la que γ se puede elegir por ancho sin miedo: la garantía
    conforme no depende de que σ̂ sea correcta. Si σ̂ fuera basura, el intervalo
    saldría ancho pero seguiría cubriendo.
    """
    rng = np.random.default_rng(43)
    n = 2000
    y = rng.normal(0, 1, n)
    pred = np.zeros(n)
    basura = np.exp(rng.normal(0, 2, n))        # σ̂ sin ninguna relación con y
    cal, pru = slice(0, 1000), slice(1000, n)
    for gamma in (0.0, 0.5, 4.0):
        s = basura + gamma
        c = conforme.calibrar_normalizado(y[cal], pred[cal], s[cal], ALPHA)
        lo, hi = conforme.aplicar_normalizado(pred[pru], s[pru], c)
        cob = float(((y[pru] >= lo) & (y[pru] <= hi)).mean())
        assert cob >= 1 - ALPHA - 0.03, f"γ={gamma} rompió la cobertura ({cob:.3f})"
