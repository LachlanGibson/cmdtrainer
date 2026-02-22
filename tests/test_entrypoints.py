import cmdtrainer.__main__ as module_main


def test_module_entrypoint_calls_main_entry(monkeypatch) -> None:
    called = {"value": 0}
    monkeypatch.setattr(module_main, "main_entry", lambda: called.__setitem__("value", 1))
    module_main.main()
    assert called["value"] == 1
