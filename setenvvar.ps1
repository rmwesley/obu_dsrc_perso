$env:EFC_SEC_CONF_PATH = Resolve-Path '..\efc_security_config_v2.0.0.json' | select -ExpandProperty Path
$env:PYTHONPATH="$PYTHONPATH;."