"""BETA-AUDIT-01: aviso de mutacion asentada para que el host persista.

Los servicios de ``packages/application`` mutan el ``Project`` **en memoria** y no
escriben a disco: en toda la capa solo ``ProjectService.save`` llama a
``store.save()``. Hasta este ticket, la unica forma de que una edicion llegara al
fichero era que algo ajeno al formulario disparase un guardado (riego, aceptar un
ajuste estructural, la pildora «Guardar» o el dialogo de cierre) — asi que una
caida del proceso perdia todo lo escrito desde el ultimo de esos eventos.

El enganche vive en los CONTROLADORES (capa de host) y no en cada panel: asi
cubre tambien las superficies que mutan sin formulario (arrastrar un lapso de vida,
crear una relacion en el Mapa, convertir un fantasma). No rompe la regla «la UI
nunca escribe persistencia directamente»: se sigue pasando por ``ProjectService``.
"""

from __future__ import annotations

from typing import Any, Callable

from packages.domain.result import Error


class MutationNotifier:
    """Mixin: avisa de una mutacion para que el host programe su guardado diferido.

    ``on_mutated`` lo inyecta ``MainWindow`` al construir los controladores. Si nadie
    lo inyecta (tests de controlador aislados, CLI historico) el mixin es inerte.
    """

    on_mutated: Callable[[], None] | None = None

    def _notify_mutation(self, result: Any) -> Any:
        """Devuelve ``result`` intacto; avisa salvo que la operacion fallara.

        Se omite el aviso solo ante ``Error`` explicito: un guardado de mas es
        inofensivo (coalesce en la ventana de antirrebote), pero uno de menos
        pierde datos del usuario.
        """
        if self.on_mutated is not None and not isinstance(result, Error):
            try:
                self.on_mutated()
            except Exception:  # noqa: BLE001 — persistir nunca debe romper la edicion
                pass
        return result
