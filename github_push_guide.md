# **🚀 Guia Prático de Git, GitHub e Versionamento Auditável**

> **Manual de Operação e Boas Práticas**

> **Foco:** Rastreabilidade, Padrões de Commit para Governança e Deploy do Projeto

## **📌 Por que o Versionamento Rígido é Essencial na Governança de IA?**

Em ambientes sujeitos a auditoria regulatória (como no setor bancário e de seguros), um modelo não pode ser alterado de forma opaca. Todo commit representa uma **mudança no ciclo de vida do modelo** e deve ser rastreável até o desenvolvedor, a data e a justificativa da alteração.

## **🛠️ Passo a Passo Completo de Sincronização**

### **1\. Verificar o Estado Atual dos Arquivos**

git status

Este comando exibirá os arquivos modificados e não rastreados (*Untracked files*).

### **2\. Configurar o .gitignore (Segurança e Governança)**

Certifique-se de que chaves de API e arquivos locais temporários não sejam publicados no repositório público:

\# Arquivos de ambiente e segredos  
.env  
\*.pem

\# Bancos locais temporários e artefatos MLflow  
futebol.db  
mlflow.db  
mlruns/  
\_\_pycache\_\_/  
venv/  
.pytest\_cache/

### **3\. Adicionar os Arquivos à Staging Area**

\# Adicionar todos os arquivos rastreados e novos  
git add .

\# Ou adicionar individualmente (recomendado para maior controle):  
git add app.py config.yaml drift\_detector.py lifecycle\_tracker.py README.md mrm\_governance\_plan.md sql\_analytics\_plan.md github\_push\_guide.md linkedin\_post\_futebol\_analytics.md MODEL\_CARD.md

### **4\. Criar o Commit com Mensagens Padronizadas (*Conventional Commits*)**

Para garantir qualidade de auditoria, utilize prefixos claros:

* feat: Nova funcionalidade no código ou dashboard.  
* docs: Alterações em documentação ou planos de governança.  
* fix: Correção de bugs no motor estatístico ou queries.  
* refactor: Melhorias na estrutura do código sem alterar comportamento.

git commit \-m "docs(governance): adiciona guias de MRM, SQL Analytics e preparatorio para entrevista"

### **5\. Enviar as Alterações para o GitHub (Push)**

\# Verificar a branch atual  
git branch

\# Enviar para a branch principal (main ou master)  
git push origin main

## **🔄 Fluxo de Resolução de Conflitos Rápidos**

Caso tenha atualizado o README ou outro arquivo direto na interface web do GitHub:

\# Baixar alterações mantendo suas mudanças locais organizadas  
git pull origin main \--rebase

\# Enviar novamente  
git push origin main

* 