"""Criterio de puerta trasera sobre un grafo causal.

Responde la pregunta que ninguna herramienta estadistica responde y que todo
economista aplicado tiene que contestar todos los dias: **que variables meto de
control**.

La practica comun —«meto todas las que tengo»— esta demostradamente mal.
Controlar por un MEDIADOR borra justo la parte del efecto que se queria medir.
Controlar por un COLISIONADOR inventa una correlacion que no existe en los
datos. Ninguno de los dos errores deja huella en el R², en el p-valor ni en
ningun diagnostico: el modelo se ve perfecto y la respuesta es falsa.

Pearl resolvio esto hace decadas y `dagitty` lo implementa, pero vive fuera del
flujo de trabajo: hay que dibujar el grafo en otra herramienta y traducir el
resultado a mano. Aqui el lienzo YA es un grafo dirigido, asi que declarar
quien causa a quien es el gesto natural de la casa.

Lo que este modulo NO hace: descubrir la estructura causal a partir de los
datos. Eso no se puede sin supuestos fuertes, y fingir que se puede seria
exactamente la clase de deshonestidad que este producto existe para evitar. El
grafo lo pone la persona; Abak solo saca las consecuencias de lo que declaro.

Referencia: Pearl, «Causality» (2009), cap. 3. Y para la version corta y
legible, Cunningham, «Causal Inference: The Mixtape», cap. 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations

# Enumerar caminos crece de forma factorial. Un grafo causal que una persona
# declara y puede defender tiene decenas de variables, no miles; el tope existe
# para fallar con un mensaje claro en vez de colgarse.
TOPE_NODOS = 60
TOPE_CAMINOS = 20_000


class ErrorCausal(Exception):
    """El grafo declarado no sirve para razonar."""


class Papel(str, Enum):
    """Que es cada variable respecto del par (tratamiento, resultado)."""

    CONFUSOR = "confusor"
    MEDIADOR = "mediador"
    COLISIONADOR = "colisionador"
    DESCENDIENTE = "descendiente"
    PREDICTOR = "predictor"
    CAUSA_DEL_TRATAMIENTO = "causa_del_tratamiento"
    IRRELEVANTE = "irrelevante"


# Que hacer con cada papel, en español, para la tabla que ve el usuario.
CONSEJO: dict[Papel, tuple[str, str]] = {
    Papel.CONFUSOR: (
        "Inclúyela",
        "Causa tanto al tratamiento como al resultado. Si la dejas fuera, su efecto se "
        "cuela en el coeficiente que te interesa y lo sesga."),
    Papel.MEDIADOR: (
        "Déjala fuera",
        "Está en medio: el tratamiento la afecta y ella afecta al resultado. Controlarla "
        "te quita justo la parte del efecto que querías medir."),
    Papel.COLISIONADOR: (
        "Déjala fuera",
        "Es un efecto común. Controlarla ABRE un camino que estaba cerrado e inventa una "
        "correlación que no existe en la realidad."),
    Papel.DESCENDIENTE: (
        "Déjala fuera",
        "Ocurre después del tratamiento y depende de él. Meterla contamina la comparación."),
    Papel.PREDICTOR: (
        "Opcional",
        "Explica al resultado pero no al tratamiento. No sesga; incluirla suele apretar los "
        "intervalos de confianza."),
    Papel.CAUSA_DEL_TRATAMIENTO: (
        "Opcional, con cuidado",
        "Explica al tratamiento pero no al resultado. No sesga, pero le quita variación útil "
        "al tratamiento y ensancha los intervalos."),
    Papel.IRRELEVANTE: (
        "Déjala fuera",
        "Según tu grafo no conecta con esta pregunta. Incluirla sólo gasta grados de libertad."),
}


@dataclass
class GrafoCausal:
    """Un DAG: variables y flechas «causa -> efecto»."""

    arcos: list[tuple[str, str]]
    variables: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        for causa, efecto in self.arcos:
            if causa == efecto:
                raise ErrorCausal(f"«{causa}» no puede causarse a sí misma.")
            self.variables.add(causa)
            self.variables.add(efecto)
        if len(self.variables) > TOPE_NODOS:
            raise ErrorCausal(
                f"El grafo tiene {len(self.variables)} variables y el tope son {TOPE_NODOS}.")
        self._padres: dict[str, set[str]] = {v: set() for v in self.variables}
        self._hijos: dict[str, set[str]] = {v: set() for v in self.variables}
        for causa, efecto in self.arcos:
            self._padres[efecto].add(causa)
            self._hijos[causa].add(efecto)
        if (ciclo := self._buscar_ciclo()):
            raise ErrorCausal(
                "Las flechas forman un ciclo: " + " → ".join(ciclo) +
                ". Un grafo causal no puede tener ciclos: si A causa a B y B causa a A, no hay "
                "manera de saber cuál mover primero.")

    # -- estructura ----------------------------------------------------------

    def _buscar_ciclo(self) -> list[str] | None:
        estado: dict[str, int] = {}   # 0 sin ver, 1 en la pila, 2 terminado
        pila: list[str] = []

        def visitar(v: str) -> list[str] | None:
            estado[v] = 1
            pila.append(v)
            for h in sorted(self._hijos[v]):
                if estado.get(h, 0) == 1:
                    return pila[pila.index(h):] + [h]
                if estado.get(h, 0) == 0 and (c := visitar(h)):
                    return c
            estado[v] = 2
            pila.pop()
            return None

        for v in sorted(self.variables):
            if estado.get(v, 0) == 0 and (c := visitar(v)):
                return c
        return None

    def padres(self, v: str) -> set[str]:
        return self._padres.get(v, set())

    def hijos(self, v: str) -> set[str]:
        return self._hijos.get(v, set())

    def _alcanzables(self, semillas: set[str], vecinos) -> set[str]:
        vistos: set[str] = set()
        pila = list(semillas)
        while pila:
            v = pila.pop()
            for w in vecinos(v):
                if w not in vistos:
                    vistos.add(w)
                    pila.append(w)
        return vistos

    def ancestros(self, v: str) -> set[str]:
        """Todo lo que llega a `v` siguiendo flechas. No se incluye a sí misma."""
        return self._alcanzables({v}, self.padres)

    def descendientes(self, v: str) -> set[str]:
        """Todo a lo que `v` llega siguiendo flechas. No se incluye a sí misma."""
        return self._alcanzables({v}, self.hijos)

    def ancestros_evitando(self, v: str, evitar: str) -> set[str]:
        """Ancestros de `v` sin pasar por `evitar`.

        Distingue lo que llega al resultado por su cuenta de lo que sólo llega
        A TRAVÉS del tratamiento. Sin esto, una causa del tratamiento parecería
        un confusor: llega a Y, sí, pero por el camino que justamente queremos
        medir, no por uno alterno.
        """
        vistos: set[str] = set()
        pila = [v]
        while pila:
            actual = pila.pop()
            for w in self.padres(actual):
                if w == evitar or w in vistos:
                    continue
                vistos.add(w)
                pila.append(w)
        return vistos

    def adyacentes(self, v: str) -> set[str]:
        return self.padres(v) | self.hijos(v)

    # -- caminos y bloqueo ---------------------------------------------------

    def caminos(self, origen: str, destino: str) -> list[list[str]]:
        """Todos los caminos SIN DIRECCIÓN entre dos variables, sin repetir nodos.

        Sin dirección porque la confusión viaja por caminos que van contra las
        flechas: si Z causa a T y a Y, el sesgo llega por T ← Z → Y, que como
        camino dirigido no existe.
        """
        for v in (origen, destino):
            if v not in self.variables:
                raise ErrorCausal(f"«{v}» no aparece en ninguna flecha del grafo.")
        encontrados: list[list[str]] = []

        def caminar(actual: str, camino: list[str], visitados: set[str]) -> None:
            if len(encontrados) >= TOPE_CAMINOS:
                raise ErrorCausal(
                    "El grafo tiene demasiados caminos para revisarlos todos. Simplifícalo: "
                    "un grafo causal que no cabe en la cabeza tampoco se puede defender.")
            if actual == destino:
                encontrados.append(camino)
                return
            for vecino in sorted(self.adyacentes(actual)):
                if vecino not in visitados:
                    caminar(vecino, camino + [vecino], visitados | {vecino})

        caminar(origen, [origen], {origen})
        return encontrados

    def es_colisionador(self, camino: list[str], i: int) -> bool:
        """¿En la posición `i` del camino chocan dos flechas: a → v ← b?"""
        v = camino[i]
        return camino[i - 1] in self.padres(v) and camino[i + 1] in self.padres(v)

    def camino_bloqueado(self, camino: list[str], condicionado: set[str]) -> bool:
        """¿Está cerrado este camino al controlar por `condicionado`?

        Un camino se bloquea en un nodo intermedio cuando:
        - es cadena (a → v → b) o bifurcación (a ← v → b) y v SÍ está controlado;
        - es colisionador (a → v ← b) y ni v ni ninguno de sus descendientes
          está controlado.

        La segunda regla es la contraintuitiva y la que cuesta dinero:
        controlar un colisionador ABRE el camino en vez de cerrarlo.
        """
        for i in range(1, len(camino) - 1):
            v = camino[i]
            if self.es_colisionador(camino, i):
                if v not in condicionado and not (self.descendientes(v) & condicionado):
                    return True      # colisionador libre: cerrado de por sí
            elif v in condicionado:
                return True          # cadena o bifurcación controlada: cerrada
        return False

    def caminos_puerta_trasera(self, tratamiento: str, resultado: str) -> list[list[str]]:
        """Los caminos que salen del tratamiento por una flecha que ENTRA a él.

        Son los que traen sesgo: no son el efecto del tratamiento, son otra cosa
        que mueve a los dos a la vez.
        """
        return [c for c in self.caminos(tratamiento, resultado)
                if len(c) > 1 and c[1] in self.padres(tratamiento)]

    def cumple_puerta_trasera(self, tratamiento: str, resultado: str,
                              ajuste: set[str]) -> bool:
        """¿`ajuste` identifica el efecto de `tratamiento` sobre `resultado`?"""
        if ajuste & self.descendientes(tratamiento):
            return False
        if tratamiento in ajuste or resultado in ajuste:
            return False
        return all(self.camino_bloqueado(c, ajuste)
                   for c in self.caminos_puerta_trasera(tratamiento, resultado))


def conjunto_ajuste(grafo: GrafoCausal, tratamiento: str, resultado: str,
                    disponibles: set[str] | None = None) -> set[str] | None:
    """El conjunto MÍNIMO de controles que identifica el efecto.

    `None` significa que con las variables disponibles NO se puede: hay
    confusión que no se puede cerrar, y ninguna regresión lo va a arreglar. Es
    un resultado, no un fallo — y es mejor saberlo antes de publicar el número.
    """
    candidatas = set(grafo.variables) - {tratamiento, resultado}
    candidatas -= grafo.descendientes(tratamiento)
    if disponibles is not None:
        candidatas &= disponibles

    if not grafo.cumple_puerta_trasera(tratamiento, resultado, candidatas):
        return None

    # Minimizar: se intenta quitar una por una, en orden estable, y se conserva
    # el recorte mientras el criterio siga cumpliéndose. Da un conjunto minimal
    # (no se le puede quitar nada), que es lo que se necesita en la práctica.
    minimo = set(candidatas)
    for v in sorted(candidatas):
        if grafo.cumple_puerta_trasera(tratamiento, resultado, minimo - {v}):
            minimo.discard(v)
    return minimo


def clasificar(grafo: GrafoCausal, tratamiento: str, resultado: str,
               ajuste: set[str] | None = None) -> dict[str, Papel]:
    """Qué papel juega cada variable respecto de la pregunta causal.

    El orden de las preguntas importa. Una variable puede cumplir varias
    descripciones a la vez, y la que manda es la que decide qué hacer con ella:
    si viene después del tratamiento no se controla, pase lo que pase.
    """
    papeles: dict[str, Papel] = {}
    ajuste = ajuste or set()
    desc_t = grafo.descendientes(tratamiento)
    anc_y = grafo.ancestros(resultado)
    anc_t = grafo.ancestros(tratamiento)
    # Lo que llega al resultado sin pasar por el tratamiento: ésa es la marca
    # de un camino alterno, y sin ella una causa del tratamiento se confunde
    # con un confusor.
    anc_y_alterno = grafo.ancestros_evitando(resultado, tratamiento)

    colisionadores: set[str] = set()
    for camino in grafo.caminos_puerta_trasera(tratamiento, resultado):
        for i in range(1, len(camino) - 1):
            if grafo.es_colisionador(camino, i):
                colisionadores.add(camino[i])

    for v in sorted(grafo.variables - {tratamiento, resultado}):
        if v in desc_t:
            # Viene DESPUÉS del tratamiento: no se controla nunca.
            papeles[v] = Papel.MEDIADOR if v in anc_y else Papel.DESCENDIENTE
        elif v in ajuste:
            papeles[v] = Papel.CONFUSOR
        elif v in colisionadores:
            papeles[v] = Papel.COLISIONADOR
        elif v in anc_t and v in anc_y_alterno:
            # Confusor que el conjunto mínimo no necesitó porque otra variable
            # ya cierra ese camino.
            papeles[v] = Papel.CONFUSOR
        elif v in anc_y_alterno:
            papeles[v] = Papel.PREDICTOR
        elif v in anc_t:
            papeles[v] = Papel.CAUSA_DEL_TRATAMIENTO
        else:
            papeles[v] = Papel.IRRELEVANTE
    return papeles


def conjuntos_alternativos(grafo: GrafoCausal, tratamiento: str, resultado: str,
                           disponibles: set[str] | None = None,
                           tope: int = 6) -> list[set[str]]:
    """Otros conjuntos que también identifican el efecto.

    Sirven para lo que Pearl llama pruebas de robustez: si dos conjuntos válidos
    y distintos dan coeficientes muy diferentes, el grafo declarado está mal.
    """
    candidatas = sorted((set(grafo.variables) - {tratamiento, resultado})
                        - grafo.descendientes(tratamiento)
                        & (disponibles if disponibles is not None else grafo.variables))
    validos: list[set[str]] = []
    for k in range(len(candidatas) + 1):
        for combo in combinations(candidatas, k):
            z = set(combo)
            if grafo.cumple_puerta_trasera(tratamiento, resultado, z):
                if not any(otro < z for otro in validos):
                    validos.append(z)
            if len(validos) >= tope:
                return validos
    return validos
