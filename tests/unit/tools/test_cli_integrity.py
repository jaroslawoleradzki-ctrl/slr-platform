from app.tools.integrity import build_parser


def test_cli_parser_positional_project_id() -> None:
    parser = build_parser()
    args = parser.parse_args(["lean_energy", "-d", "custom.db", "--json"])
    assert args.project_id == "lean_energy"
    assert args.db_path == "custom.db"
    assert args.output_json is True
