import app
from modules import *

_app = app.App()

_app.addModule(PrivSystem)
_app.addModule(MiscCommands)
_app.addModule(Music)

_app.run()