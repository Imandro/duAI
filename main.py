import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="duAI", description="duAI - Don't Use AI")
    parser.add_argument("--panic", action="store_true", help="Ejecuta limpieza total silenciosa y sale")
    args = parser.parse_args()

    if args.panic:
        from duai.core.panic import format_result_summary, perform_panic

        result = perform_panic()
        print(format_result_summary(result))
        return 0

    from duai.app import run_gui

    sys.exit(run_gui())


if __name__ == "__main__":
    raise SystemExit(main())
