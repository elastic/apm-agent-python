import cli
from click.testing import CliRunner

# This tests are really slow at the moment since they actually run the commands


def test_help():
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "help" in result.output


def test_command_generate_with_force():
    runner = CliRunner()
    result = runner.invoke(cli.main, ["generate", "--force"])
    assert result.exit_code == 0
    assert "Generating" in result.output


def test_command_build():
    runner = CliRunner()
    result = runner.invoke(cli.main, ["build"])
    assert result.exit_code == 0
    assert "succeeded" in result.output


def test_command_test():
    runner = CliRunner()
    result = runner.invoke(cli.main, ["test"])
    assert result.exit_code == 0
    assert "Results are now ready" in result.output
