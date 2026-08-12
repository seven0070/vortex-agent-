"""Communication capability — uses glossopetrae, etc."""
from ..legacy import GlossopetraeTool, SteganographyTool

class TranslateTool(GlossopetraeTool):
    name = "communication.translate"
    category = "communication"

class StegoEncodeTool(SteganographyTool):
    name = "communication.hide"
    category = "communication"

COMM_TOOLS = [TranslateTool, StegoEncodeTool]
