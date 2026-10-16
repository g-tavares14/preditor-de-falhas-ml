"""Microserviço do modelo: abre a Random Forest exportada e responde `POST /prever` (SPEC-api-csharp.md, módulo `servico-modelo`).

Só a biblioteca padrão para o HTTP; scikit-learn e pandas para o modelo. Sem Spark e sem Java. Quem chama é a API em C#,
na rede interna: este serviço não é público.
"""
