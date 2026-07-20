"""Brisa del Mapa (BETA2-PULIDO-07): impulso puro del motor de física."""

from __future__ import annotations

import math

from packages.ui.graph_physics import Body, PhysicsEngine


def _engine():
    engine = PhysicsEngine()
    engine.set_world(
        [
            Body(body_id="viva", x=0.0, y=0.0),
            Body(body_id="congelada", x=100.0, y=0.0, pinned=True),
            Body(body_id="viva2", x=200.0, y=0.0),
        ],
        [],
    )
    return engine


class TestApplyBreeze:
    def test_breeze_pushes_live_bodies_only(self):
        engine = _engine()
        engine.apply_breeze(0.0, strength=1.0)  # ángulo 0 → viento hacia +x
        assert engine.bodies["viva"].vx > 0.0
        assert engine.bodies["viva2"].vx > 0.0
        # Las congeladas del jardín (pinned) ni se inmutan.
        assert engine.bodies["congelada"].vx == 0.0
        assert engine.bodies["congelada"].vy == 0.0

    def test_breeze_varies_per_body_but_is_deterministic(self):
        first = _engine()
        second = _engine()
        first.apply_breeze(math.pi / 3, strength=0.6)
        second.apply_breeze(math.pi / 3, strength=0.6)
        # Determinista: mismo ángulo → mismos impulsos.
        for body_id in ("viva", "viva2"):
            assert first.bodies[body_id].vx == second.bodies[body_id].vx
            assert first.bodies[body_id].vy == second.bodies[body_id].vy
        # Variación por cuerpo: los vivos no se mecen al unísono.
        assert first.bodies["viva"].vx != first.bodies["viva2"].vx

    def test_breeze_is_gentle(self):
        engine = _engine()
        engine.apply_breeze(1.0)  # strength por defecto
        speed = math.hypot(engine.bodies["viva"].vx, engine.bodies["viva"].vy)
        assert 0.0 < speed < 1.0  # ráfaga suave, muy por debajo del reheat (0.8·√2)
