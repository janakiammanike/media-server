from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'MediaVault Pro'
    app_version: str = '2.0.0'
    api_prefix: str = '/api'
    host: str = '0.0.0.0'
    port: int = 8000
    data_dir: Path = Path.home() / 'MediaVaultPro'

    model_config = SettingsConfigDict(
        env_prefix='MEDIAVAULT_',
        env_file='.env',
        extra='ignore',
    )

    @property
    def db_path(self) -> Path:
        return self.data_dir / 'mediavault.db'

    @property
    def storage_dir(self) -> Path:
        return self.data_dir / 'storage'

    @property
    def cloud_dir(self) -> Path:
        return self.storage_dir / 'cloud'

    @property
    def thumbs_dir(self) -> Path:
        return self.storage_dir / 'thumbnails'

    @property
    def artwork_dir(self) -> Path:
        return self.storage_dir / 'artwork'


settings = Settings()
