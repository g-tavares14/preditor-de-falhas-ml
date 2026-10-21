"""Microserviço do modelo: abre a Random Forest exportada e responde `POST /prever` (SPEC-api-csharp.md, módulo `servico-modelo`; o chamador passou do C# para o Go em SPEC-go-react.md).

Só a biblioteca padrão para o HTTP; scikit-learn e pandas para o modelo. Sem Spark e sem Java. Quem chama é o servidor em Go,
na rede interna: este serviço não é público.
"""
