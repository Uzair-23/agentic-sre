import os
import logging
from dotenv import load_dotenv
from langfuse import Langfuse

# Force logging to show up
logging.basicConfig(level=logging.DEBUG)

load_dotenv()
print(f"Loaded Host: {os.getenv('LANGFUSE_HOST')}")
print(f"Has Public Key: {bool(os.getenv('LANGFUSE_PUBLIC_KEY'))}")
print(f"Has Secret Key: {bool(os.getenv('LANGFUSE_SECRET_KEY'))}")

# Initialize raw Langfuse client
langfuse = Langfuse()

# Create a dummy trace
print("Creating trace...")
trace = langfuse.trace(name="Isolation-Test-Trace")
trace.span(name="Hello-World-Span")

# Force flush
print("Flushing to server...")
langfuse.flush()
print("Done!")