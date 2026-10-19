import pytest
from src.config_loader import get_mapping, ConfigError


def test_mapping_real_carga():
    """El YAML real del repo debe cargar sin error."""
    get_mapping.cache_clear()
    m = get_mapping()
    assert m.version == 1
    assert "rut" in m.campos
    assert m.campos["rut"].tipo == "string"
    assert m.campos["rut"].obligatorio is True
    assert m.campos["rut"].fuente == "rut_postulante"


def test_mapping_roto_falla(tmp_path, monkeypatch):
    """YAML con tipo inválido debe levantar ConfigError."""
    (tmp_path / "mapping_serviu.yaml").write_text(
        "version: uno\n"
        "campos:\n"
        "  rut:\n"
        "    tipo: string\n"
        "    obligatorio: true\n"
        "    fuente: x\n"
    )
    (tmp_path / "base_schema.json").write_text('{"type":"object"}')
    monkeypatch.setenv("DEPA_CONFIG_DIR", str(tmp_path))
    get_mapping.cache_clear()
    with pytest.raises(ConfigError):
        get_mapping()
    get_mapping.cache_clear()
