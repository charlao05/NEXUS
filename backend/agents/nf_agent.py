from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..utils.logging_utils import get_logger
from backend.utils.llm_client import gerar_texto_simples

logger = get_logger(__name__)


def load_sales(path: str | Path) -> Optional[Dict[str, Any]]:
    """Carrega um arquivo JSON com registros de vendas.

    Retorna um dicionário com os dados se o arquivo existir e for JSON válido.
    - Se o arquivo não existir, retorna `None`.
    - Se o JSON for inválido, lança `ValueError`.

    :param path: caminho para o arquivo JSON de vendas.
    :return: dicionário com os dados ou `None` se não existir.
    """
    path = Path(path)
    if not path.exists():
        logger.warning("Arquivo de vendas não encontrado: %s", path)
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("JSON inválido em %s: %s", path, e)
        raise ValueError(f"JSON inválido: {e}") from e
    return data


def _get_field(record: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Tenta obter o primeiro valor disponível entre chaves alternativas."""
    for k in keys:
        if k in record and record[k] is not None:
            return record[k]
    return default


def prepare_invoice_steps(sales_record: Dict[str, Any]) -> Dict[str, Any]:
    """Monta os passos e uma explicação para emitir uma NFS-e com base em um registro de venda.

    Aceita chaves em português ou inglês (por exemplo `cliente_nome` ou `client_name`).

    Retorna um dicionário com campos:
      - `steps`: lista de passos (List[str])
      - `explicacao`: texto gerado pelo LLM (ou texto fallback)
      - `missing_fields`: (opcional) lista de campos obrigatórios ausentes

    :param sales_record: dicionário com dados da venda.
    :return: dicionário com instruções para emissão da nota fiscal.
    """
    # Valores compatíveis (suporte a chaves em pt/en)
    cliente = _get_field(sales_record, "cliente_nome", "client_name", default="Cliente")
    cpf_cnpj = _get_field(sales_record, "cliente_cnpj_cpf", "client_id", default=None)
    amount = _get_field(sales_record, "valor_total", "amount", default=0.0)
    descricao = _get_field(
        sales_record, "descricao_servicos", "description", default=None
    )
    data_venda = _get_field(sales_record, "data_venda", "date", default=None)

    required = {
        "cliente_nome": cliente,
        "cliente_cnpj_cpf": cpf_cnpj,
        "valor_total": amount,
        "descricao_servicos": descricao,
        "data_venda": data_venda,
    }

    missing = [k for k, v in required.items() if v in (None, "", 0.0)]

    steps: List[str] = [
        "Acesse o sistema de NFS-e da prefeitura (site ou portal municipal)",
        "Faça login com sua conta MEI",
    ]

    if cliente:
        steps.append(f"Preencha dados do cliente: {cliente}")
    else:
        steps.append("Preencha dados do cliente: <NOME_DO_CLIENTE>")

    if cpf_cnpj:
        steps.append(f"Informe CPF/CNPJ do cliente: {cpf_cnpj}")

    steps.append(f"Informe o valor: R$ {float(amount):.2f}")

    if descricao:
        steps.append(f"Descreva os serviços/produtos: {descricao}")

    if data_venda:
        steps.append(f"Informe a data de emissão/prestação: {data_venda}")

    steps.append("Gere e salve a NFS-e (XML/PDF) e envie para o cliente, se aplicável")

    prompt = (
        "Explique de forma simples e direta, para um microempreendedor (MEI), "
        f"como emitir uma NFS-e para uma venda de R$ {float(amount):.2f}. "
        "Inclua os principais campos necessários, onde encontrá-los no portal municipal e "
        "um tom amigável e prático. Não use linguagem técnica desnecessária. "
    )

    # Enriquecer prompt com resumo da venda
    resumo = f"Cliente: {cliente}; Valor: R$ {float(amount):.2f}"
    if descricao:
        resumo += f"; Serviço: {descricao}"
    prompt = resumo + ". " + prompt

    try:
        explicacao = gerar_texto_simples(prompt)
    except Exception as e:
        logger.warning("LLM falhou ao gerar explicação: %s", e)
        explicacao = (
            "Siga os passos listados para emitir a nota fiscal no portal da prefeitura."
        )

    result: Dict[str, Any] = {"steps": steps, "explicacao": explicacao}
    if missing:
        logger.warning("Campos obrigatórios ausentes no registro de venda: %s", missing)
        result["missing_fields"] = missing

    return result


if __name__ == "__main__":
    example_sale = {
        "cliente_nome": "Fulano da Silva",
        "cliente_cnpj_cpf": "123.456.789-00",
        "valor_total": 250.0,
        "descricao_servicos": "Serviço de manutenção",
        "data_venda": "2025-11-17",
    }
    out = prepare_invoice_steps(example_sale)
    print(out["explicacao"])
