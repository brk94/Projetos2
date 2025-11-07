# Projetos 2 - Grupo 1
# MC Sonae — Visão Geral & Fluxo do Projeto

> **Objetivo**: Centralizar relatórios de projetos por área (PDF/DOCX/XLSX), extrair informações-chave (KPIs, marcos, orçamento) e apresentar dashboards para tomada de decisão — com **controle de acesso por perfil (RBAC)** e **API** documentada.

## Sumário
- [1. Visão Geral](#1-visão-geral)
- [2. Fluxo de Ponta a Ponta](#2-fluxo-de-ponta-a-ponta)
- [3. Arquitetura & Principais Módulos](#3-arquitetura--principais-módulos)
- [4. Papéis & Permissões (RBAC)](#4-papéis--permissões-rbac)
- [5. Como Executar (setup rápido)](#5-como-executar-setup-rápido)
- [6. Variáveis de Ambiente](#6-variáveis-de-ambiente)
- [7. Fluxo Detalhado](#7-fluxo-detalhado)
- [8. APIs & Contratos](#8-apis--contratos)
- [9. Banco de Dados (ORM)](#9-banco-de-dados-orm)
- [10. Segurança (JWT + Refresh)](#10-segurança-jwt--refresh)
- [11. Roteiro de Demonstração](#11-roteiro-de-demonstração)
- [12. Roadmap](#12-roadmap)

---

## 1. Visão Geral
O sistema integra **Frontend (Streamlit)**, **API (FastAPI)** e **Dados (SQLAlchemy/MySQL)**. O usuário faz **login**, envia **relatórios por área** (ex.: TI), o **parser** interpreta o conteúdo e **persiste** no banco. As **telas de dashboard** leem da API e exibem KPIs e marcos.

---

## 2. Fluxo de Ponta a Ponta

<pre>
[Login (Streamlit)]
  │  gera JWT (access) + refresh
  ▼
[Menu por Perfil / RBAC]
  │  UI mostra só o que o perfil pode acessar
  ├──► [Admin: Usuários &amp; Permissões] ──► (valida na API)
  │
  ▼
[Upload de Relatório (TI)]
  │  envia arquivo → API valida e roteia
  ▼
[API FastAPI: validação e roteamento]
  │  chama fábrica de parsers por área
  ▼
[Factory → Parser (ex.: TI)]
  │  extrai KPIs, marcos, período/sprint, etc.
  ▼
[Serviços / ORM]
  │  persiste dados
  ▼
(MySQL)
  │  dashboards consultam via API
  ▼
[Dashboards (TI) via API]
</pre>

Resumo: **Login** gera token → **permissões** moldam a UI → **Upload** aciona **parser** → **persistência** no **MySQL** → **dashboards** consomem a API.

---

## 3. Arquitetura & Principais Módulos

### Frontend (Streamlit)
- `Home.py`: Login e landing pós-login.
- `ui_nav.py`: Sidebar/menu customizado (RBAC, logout).
- `2_Processar_Relatórios.py`: Upload e envio de relatórios; polling.
- `3_Dashboard.py`: Visualizações (TI completo; demais áreas em mock).
- `Admin_Usuarios.py`: Gestão de usuários (em evolução).
- `7_About.py`: Contexto acadêmico e instruções.

### Backend (FastAPI)
- `main.py`: Inicialização da API, rotas e proteção por permissões.
- `auth.py`: Autenticação JWT (access/refresh) e dependências de segurança.
- `services.py`: Camada de serviços/repositórios (regras de persistência/leitura).
- `models.py`: SQLAlchemy ORM (usuários, projetos, relatórios, KPIs, marcos...).
- `config.py` / `constants.py` / `utils.py`: Configurações e utilitários.

### Parsing
- `factory.py`: Seleciona o parser pela **área** do relatório.
- `parser_ti.py`: Parser da área **TI** (PDF/DOCX/XLSX). **Objetivo**: extrair KPIs, marcos, período/sprint, etc.

---

## 4. Papéis & Permissões (RBAC)
Papéis previstos (exemplos): **Administrador**, **Diretor**, **Gestor de Projetos**, **Analista**, **Visualizador**.  
A **API** valida as permissões nas rotas sensíveis e o **Frontend** esconde itens de menu/ações que o perfil não deve ver.

---

## 5. Como Executar (setup rápido)

### 5.1. Requisitos
- Python 3.10+
- MySQL (local ou nuvem)
- Virtualenv recomendado

### 5.2. Backend (API)
```bash
# criar venv e instalar dependências
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt

# executar API (ajuste host/porta conforme necessário)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5.3. Frontend (Streamlit)
```bash
# no mesmo venv (ou outro), instale dependências do front se separadas
streamlit run Home.py
# as demais páginas aparem no multipage (Processar Relatórios, Dashboard, Admin, About)
```

---

## 6. Variáveis de Ambiente
- **API_URL**: URL base da API FastAPI usada pelo Streamlit (ex.: `http://127.0.0.1:8000`).
- **JWT settings** (no backend): tempo de expiração do access token, janela/estratégia de refresh, chave secreta, etc.
- Demais chaves: credenciais do banco, flags de debug, etc.

> **Dica**: use arquivos `.env` (não versione dados sensíveis).

---

## 7. Fluxo Detalhado

1) **Login**
   - Usuário entra com e-mail/senha → API emite **JWT access** (curta duração) e **refresh** (renovação de sessão).
   - O **menu** da sidebar é montado com base no **papel** do usuário.

2) **Upload de Relatórios**
   - Na página *Processar Relatórios*, o usuário seleciona o **tipo/área** e envia o arquivo (ex.: TI).
   - A API valida permissões e chama a **factory** → **parser** da área.

3) **Parsing & Persistência**
   - O parser extrai **KPIs**, **marcos**, período/sprint, etc.
   - Via `services.py`, os dados são gravados no **MySQL** (modelos do `models.py`).

4) **Dashboards**
   - A página *Dashboard* requisita dados à API e exibe **métricas**, **status** e **marcos**.
   - TI está **end‑to‑end** funcional; demais áreas estão **mockadas** para expansão.

5) **Admin**
   - Gestão de usuários/permissões e vinculação **projeto × setor × papel** (em evolução).

---

## 8. APIs & Contratos
- A API segue o padrão FastAPI com documentação **OpenAPI** em `/docs` e `/redoc`.
- Endpoints típicos:
  - **Auth**: login/refresh/logout.
  - **Relatórios**: upload/processamento/consulta por área.
  - **Dashboards**: agregações por projeto/sprint/área.
  - **Admin**: usuários, papéis e permissões.
- **Recomendação**: manter um *Anexo de API* com exemplos de request/response por endpoint.

---

## 9. Banco de Dados (ORM)
Entidades principais (exemplos): **Usuário**, **Projeto**, **Relatório**, **KPI**, **Marco** (e relações auxiliares).  
O `models.py` define classes **SQLAlchemy** com `__tablename__` e mapeamentos. Quando necessário, **DTOs Pydantic** são usados para entrada/saída na API (com `from_attributes=True` onde aplicável).

---

## 10. Segurança (JWT + Refresh)
- **Autenticação**: JWT Access (curta duração) + **Refresh** para renovar sessão.
- **Autorização**: Depêndencias/guards validam **permissões por rota**; o front **esconde** ações não permitidas.
- **Boas práticas**: cookies HttpOnly/SameSite (quando aplicável), expiração curta do access token, rotação, invalidação de sessões, logs de segurança.

---

## 11. Roteiro de Demonstração
1. **Login** com usuário de demonstração; mostrar que o menu muda pelo papel.
2. **Upload (TI)** de um arquivo e explicar **parsing** (o que é extraído).
3. Abrir **Dashboard (TI)** e evidenciar os dados populados.
4. Comentar **Admin** e **roadmap** de expansão (Retalho/RH/Marketing).