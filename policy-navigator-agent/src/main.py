from typing import Optional

import typer

from agent import run

app = typer.Typer(add_completion=False)


@app.command()
def main(
    profile: str = typer.Option(..., "--profile", help="사용자 프로필 문자열 (예: '29세/수도권/중소기업/월250/미혼')"),
    pdf: Optional[str] = typer.Option(None, "--pdf", help="정책 PDF 경로 (기본: data/finance_policy.pdf. 예: data/transportation_policy.pdf)"),
) -> None:
    result = run(profile=profile, pdf_path=pdf)
    print(result)


if __name__ == "__main__":
    app()
