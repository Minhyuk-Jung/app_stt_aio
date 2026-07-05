
def test_config_injector_property_requires_bind(tmp_path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "props.db", migrate_backup=False) as config:
        try:
            _ = config.injector
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass
        config.bind_injector()
        assert config.injector is config._injector


def test_config_pipeline_property_requires_bind(tmp_path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "pipeline_props.db", migrate_backup=False) as config:
        try:
            _ = config.pipeline
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass
        bound = config.bind_pipeline()
        assert config.pipeline is bound
        assert config.bind_pipeline() is bound
