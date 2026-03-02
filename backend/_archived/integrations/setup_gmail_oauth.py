#!/usr/bin/env python
"""Assistente interativo para configurar OAuth do Gmail com opções avançadas.

Recursos:
- Aceita caminhos customizados para o `credentials.json` do Google Cloud.
- Permite escolher onde salvar o token autorizado (`gmail_authorized_user.json`).
- Reaproveita tokens existentes (faz refresh automático quando possível).
- Oferece a flag `--force` para forçar um novo fluxo OAuth via navegador.

Execução básica:
    python -m src.integrations.setup_gmail_oauth

Exemplo com paths customizados:
    python -m src.integrations.setup_gmail_oauth \\
        --credentials-file config/google/credentials.json \\
        --output-file config/google/gmail_authorized_user.json
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence


DEFAULT_CREDENTIALS = Path("credentials.json")
DEFAULT_OUTPUT = Path("gmail_authorized_user.json")
DEFAULT_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configura credenciais OAuth para Gmail API (escopo gmail.send)."
    )
    parser.add_argument(
        "--credentials-file",
        default=str(DEFAULT_CREDENTIALS),
        help="Caminho para o client ID OAuth baixado do Google Cloud Console.",
    )
    parser.add_argument(
        "--output-file",
        default=str(DEFAULT_OUTPUT),
        help="Arquivo onde o token autorizado será salvo (default: gmail_authorized_user.json).",
    )
    parser.add_argument(
        "--scope",
        action="append",
        dest="scopes",
        help="Escopos adicionais (pode repetir a flag). Por padrão usa apenas gmail.send.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignora tokens existentes e força novo fluxo OAuth em navegador.",
    )
    return parser.parse_args()


def _carregar_dependencias():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
    except ImportError:
        print("[ERROR] Dependências OAuth não instaladas.")
        print("Execute: pip install google-auth-oauthlib google-auth")
        raise
    return InstalledAppFlow, Request, Credentials


def _salvar_credenciais(creds, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        f.write(creds.to_json())


def _mostrar_instrucao_env(output_file: Path) -> None:
    abs_path = output_file.resolve()
    print("\n[Próximos passos]")
    print(f'1. Abra seu .env e adicione/atualize: GMAIL_CREDENTIALS_FILE="{abs_path}"')
    print('2. Defina também SENDER_EMAIL="seu-email@gmail.com" (ou conta equivalente)')
    print(
        "3. Para testar o envio real: python -m src.orchestrator nf --sales-file data/test_sale_gmail.json --send-gmail"
    )
    print()


def _tentar_reuso(
    output_file: Path, scopes: Sequence[str], force: bool, Request, Credentials
) -> bool:
    if not output_file.exists() or force:
        return False

    try:
        creds = Credentials.from_authorized_user_file(str(output_file), scopes)
    except Exception as exc:  # noqa: BLE001
        print(
            f"[WARN] Não foi possível carregar token existente ({exc}). Gerando novo fluxo..."
        )
        return False

    if creds and creds.valid:
        print("[Info] Token existente ainda é válido. Nenhuma ação necessária.")
        _mostrar_instrucao_env(output_file)
        return True

    if creds and creds.expired and creds.refresh_token:
        print("[Info] Token existente expirado. Tentando refresh automático...")
        try:
            creds.refresh(Request())
            _salvar_credenciais(creds, output_file)
            print("[Success] Token renovado com sucesso sem abrir navegador.")
            _mostrar_instrucao_env(output_file)
            return True
        except Exception as exc:  # noqa: BLE001
            print(
                f"[WARN] Refresh automático falhou ({exc}). Será necessário novo fluxo OAuth."
            )

    return False


def setup_gmail_oauth(
    credentials_file: Path,
    output_file: Path,
    scopes: Sequence[str],
    force: bool = False,
) -> bool:
    InstalledAppFlow, Request, Credentials = _carregar_dependencias()

    credentials_file = credentials_file.expanduser()
    output_file = output_file.expanduser()

    if _tentar_reuso(output_file, scopes, force, Request, Credentials):
        return True

    if not credentials_file.exists():
        print(f"[ERROR] Arquivo {credentials_file} não encontrado.")
        print("\nPassos para obter o arquivo:")
        print("1. Vá para https://console.cloud.google.com/apis/credentials")
        print("2. Clique 'Create Credentials' → 'OAuth 2.0 Client IDs'")
        print("3. Selecione 'Desktop application'")
        print("4. Faça download do JSON e informe o caminho via --credentials-file")
        return False

    print("[Info] Iniciando fluxo OAuth do Gmail...")
    print("[Info] Um navegador será aberto pedindo autorização.")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), scopes)

        # Se o arquivo de credenciais estiver configurado com redirect tipo "urn:ietf:wg:oauth:2.0:oob",
        # usamos run_console (mostra código para copiar/colar). Caso contrário, mantemos run_local_server.
        redirect_uris = flow.client_config.get("redirect_uris", []) or []
        use_console = any(
            uri.startswith("urn:ietf:wg:oauth:2.0:oob") for uri in redirect_uris
        )

        if use_console:
            print("[Info] Detectado fluxo OOB (urn:ietf:wg:oauth:2.0:oob).")
            print(
                "[Ação] Copie a URL abaixo, abra no navegador, autorize e cole o código gerado:"
            )
            auth_url, _ = flow.authorization_url(
                prompt="consent",
                access_type="offline",
                include_granted_scopes="true",
            )
            print("\n=== URL DE AUTORIZAÇÃO ===")
            print(auth_url)
            print("==========================\n")
            code = input("Cole aqui o código exibido após a autorização: ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials
        else:
            creds = flow.run_local_server(port=0)
        _salvar_credenciais(creds, output_file)

        print(f"\n[Success] Credenciais salvas em: {output_file.resolve()}")
        _mostrar_instrucao_env(output_file)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Falha ao configurar OAuth: {exc}")
        return False


def main() -> int:
    args = _parse_args()
    scopes = args.scopes or DEFAULT_SCOPES

    try:
        ok = setup_gmail_oauth(
            credentials_file=Path(args.credentials_file),
            output_file=Path(args.output_file),
            scopes=scopes,
            force=args.force,
        )
    except ImportError:
        return 1

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
