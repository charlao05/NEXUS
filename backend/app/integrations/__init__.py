"""
NEXUS — Camada de Integrações com APIs Governamentais e Externas
================================================================

Módulos:
- http_base: Client HTTP base assíncrono (httpx) com retry, timeout, log
- cnpj_client: Consulta CNPJ / status MEI (OpenCNPJ, CNPJá, CNPJ.ws)
- transparencia_federal_client: Portal da Transparência federal
- transparencia_vitoria_client: Transparência municipal — Vitória/ES
- transparencia_serra_client: Transparência municipal — Serra/ES
- cnd_client: Certidão Negativa de Débitos (SERPRO Conecta / terceiros)
- divida_ativa_client: Dívida Ativa da União (PGFN dados abertos + Conecta)
- nfse_nacional_client: Emissor Nacional NFS-e (padrão federal 2026+)
- nfse_aggregator_client: Agregadores de NFSe (Focus NFe, Webmania, etc.)
"""
