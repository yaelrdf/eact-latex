"""eact: convert LaTeX (or EactMaker markup) into CASIO eActivity files (.g2e).

Modules:
    container   binary file layout (.g1e/.g2e)
    charmap     CASIO character table
    ir          intermediate representation
    latex       LaTeX front-end
    eam         EactMaker markup front-end / writer
    encoder     IR -> bytes
    decoder     bytes -> IR
    preview     text preview of the calculator screen
    convert     high-level API
    cli         the `eact` command
"""
__version__ = "0.1.0"
