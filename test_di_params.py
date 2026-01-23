import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

# Use the credentials I found earlier
endpoint = "https://enc-dev-aoai-trans.cognitiveservices.azure.com/" # Wait, this is translator endpoint?
# Let me check app.py for the correct DI endpoint
# AZURE_DOC_INTEL_ENDPOINT = get_secret("AZURE_DOC_INTEL_ENDPOINT")
# In temp_app.py:
# TRANSLATOR_ENDPOINT = "https://enc-dev-aoai-trans.cognitiveservices.azure.com/"
# I need the DI endpoint.

# Let me check app.py again for DI endpoint.
