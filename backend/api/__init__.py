import sys

# Ensure langchain backward compatibility for langfuse.callback
try:
    import langchain_core.callbacks.base
    import langchain_core.agents
    import langchain_core.documents

    sys.modules.setdefault("langchain.callbacks", sys.modules.get("langchain_core.callbacks"))
    sys.modules.setdefault("langchain.callbacks.base", langchain_core.callbacks.base)
    sys.modules.setdefault("langchain.schema", sys.modules.get("langchain_core"))
    sys.modules.setdefault("langchain.schema.agent", langchain_core.agents)
    sys.modules.setdefault("langchain.schema.document", langchain_core.documents)
except ImportError:
    pass
