"""
Azure Key Vault Integration
Centralized secret management for API keys and connection strings
"""

import os
from typing import Optional, Dict
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential, ClientSecretCredential


class KeyVaultManager:
    """
    Azure Key Vault manager for centralized secret management
    
    Features:
    - Secure secret storage and retrieval
    - Automatic secret rotation support
    - Managed Identity authentication
    - Fallback to environment variables for development
    """
    
    def __init__(self, vault_url: Optional[str] = None):
        self.vault_url = vault_url or os.environ.get("AZURE_KEYVAULT_URL")
        
        if not self.vault_url:
            print("Warning: Azure Key Vault not configured. Using environment variables.")
            self.configured = False
            return
        
        self.configured = True
        
        try:
            tenant_id = os.environ.get("AZURE_TENANT_ID")
            client_id = os.environ.get("AZURE_CLIENT_ID")
            client_secret = os.environ.get("AZURE_CLIENT_SECRET")
            
            if all([tenant_id, client_id, client_secret]):
                credential = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret
                )
            else:
                credential = DefaultAzureCredential()
            
            self.client = SecretClient(vault_url=self.vault_url, credential=credential)
            print(f"Connected to Azure Key Vault: {self.vault_url}")
        except Exception as e:
            print(f"Error initializing Key Vault client: {e}")
            self.configured = False
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Retrieve a secret from Key Vault
        Falls back to environment variable if Key Vault is not configured
        
        Args:
            secret_name: Name of the secret (e.g., "OpenAI-API-Key")
            
        Returns:
            Secret value or None if not found
        """
        if not self.configured:
            env_name = secret_name.replace("-", "_").upper()
            return os.environ.get(env_name)
        
        try:
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            print(f"Error retrieving secret '{secret_name}': {e}")
            env_name = secret_name.replace("-", "_").upper()
            return os.environ.get(env_name)
    
    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Store a secret in Key Vault
        
        Args:
            secret_name: Name of the secret
            secret_value: Secret value
            
        Returns:
            True if successful, False otherwise
        """
        if not self.configured:
            print(f"Key Vault not configured. Cannot store secret '{secret_name}'")
            return False
        
        try:
            self.client.set_secret(secret_name, secret_value)
            print(f"Secret '{secret_name}' stored successfully")
            return True
        except Exception as e:
            print(f"Error storing secret '{secret_name}': {e}")
            return False
    
    def delete_secret(self, secret_name: str) -> bool:
        """
        Delete a secret from Key Vault (soft delete)
        
        Args:
            secret_name: Name of the secret to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.configured:
            print(f"Key Vault not configured. Cannot delete secret '{secret_name}'")
            return False
        
        try:
            self.client.begin_delete_secret(secret_name).wait()
            print(f"Secret '{secret_name}' deleted successfully")
            return True
        except Exception as e:
            print(f"Error deleting secret '{secret_name}': {e}")
            return False
    
    def get_all_secrets_config(self) -> Dict[str, str]:
        """
        Retrieve all configured secrets for the application
        
        Returns:
            Dictionary of secret names to values
        """
        secret_names = [
            "OpenAI-API-Key",
            "Azure-Search-Endpoint",
            "Azure-Search-API-Key",
            "Cosmos-Endpoint",
            "Cosmos-Key",
            "Confluence-Base-URL",
            "Confluence-API-Token",
            "Azure-Tenant-ID",
            "Azure-Client-ID",
            "Azure-Client-Secret"
        ]
        
        config = {}
        for name in secret_names:
            value = self.get_secret(name)
            if value:
                config[name] = value
        
        return config


keyvault = KeyVaultManager()
