#!/usr/bin/env python3
"""The Last Slayer: Project 2026. Arrows walk, Z talks, X cancels, M maps, G walks thee
to Tantegel on its own.

    .venv/bin/python main.py
"""
import save
from app import NAME, App
from field import FieldState
from title import TitleState

if __name__ == "__main__":
    app = App(f"{NAME}   [arrows: walk  Z: look  X: back  M: map  G: go to Tantegel]")
    app.push(TitleState(app))
    app.run()
    if app.states and isinstance(app.states[0], FieldState):
        save.write(app.states[0])       # quitting is the save point, so CONTINUE works
