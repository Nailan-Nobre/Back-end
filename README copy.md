# Sistema de Controle de Presença com QR Code

## ⚙️ Instalação e Configuração

### 1. Clonar o Repositório

```bash
git clone <https://github.com/scaua1675-ai/projetos.git>
```

### 2. Criar o Ambiente Virtual

Um ambiente virtual isola as dependências do projeto do Python do sistema.

#### No Windows (PowerShell):

```powershell
# Criar o ambiente virtual
python -m venv .venv

# Ativar o ambiente virtual
.\.venv\Bin\Activate.ps1
```

#### No Windows (CMD):

```cmd
# Criar o ambiente virtual
python -m venv .venv

# Ativar o ambiente virtual
.venv\Bin\activate.bat
```

### 3. Instalar as Dependências

Com o ambiente virtual ativado, instale os pacotes necessários:

```bash
pip install -r requirements.txt
```

### 4. Verificar Instalação

Para garantir que tudo foi instalado corretamente:

```bash
python -c "import flask, qrcode, pyautogui; print('Todas as dependências instaladas com sucesso!')"
```

## 🗄️ Banco de Dados

O banco de dados é inicializado automaticamente pelo `bd.py` na primeira execução.

## 🚀 Execução do Programa

### Pré-requisitos
- Ambiente virtual criado e ativado
- Todas as dependências instaladas

### Opção 1: Executar a API Flask

```bash
# Certifique-se de que o ambiente virtual está ativado
python projetos/api.py
```

**Saída esperada:**
```
 * Serving Flask app 'api'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

A API estará disponível em `http://localhost:5000`

### Opção 2: Executar o Bot de Automação

```bash
# Certifique-se de que o ambiente virtual está ativado
python projetos/bot.py
```

### Opção 3: Gerar QR Codes

```bash
# Certifique-se de que o ambiente virtual está ativado
python projetos/qr.py
```

## 👥 Equipe

<div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 6px 12px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; transition: transform 0.3s;">
<a href="https://github.com/Nailan-Nobre" target="_blank" style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 20px; width: 100%;">
<img src="https://github.com/scaua1675-ai.png" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 2px solid #e0e0e0;"/>
<div>
<h3 style="margin: 0 0 5px 0; color: #333;">Cauã</h3>
</div>
</a>
</div>

##

<div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 6px 12px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; transition: transform 0.3s;">
<a href="https://github.com/Nailan-Nobre" target="_blank" style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 20px; width: 100%;">
<img src="https://github.com/otaviogkk.png" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 2px solid #e0e0e0;"/>
<div>
<h3 style="margin: 0 0 5px 0; color: #333;">Otávio</h3>
</div>
</a>
</div>

##

<div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 6px 12px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; transition: transform 0.3s;">
<a href="https://github.com/Nailan-Nobre" target="_blank" style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 20px; width: 100%;">
<img src="https://github.com/Lincoln16yyy.png" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 2px solid #e0e0e0;"/>
<div>
<h3 style="margin: 0 0 5px 0; color: #333;">Lincoln</h3>
</div>
</a>
</div>

##

<div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 6px 12px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; transition: transform 0.3s;">
<a href="https://github.com/Nailan-Nobre" target="_blank" style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 20px; width: 100%;">
<img src="https://github.com/Nailan-Nobre.png" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 2px solid #e0e0e0;"/>
<div>
<h3 style="margin: 0 0 5px 0; color: #333;">Nailan Nobre</h3>
</div>
</a>
</div>

##

<div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 6px 12px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; transition: transform 0.3s;">
<a href="https://github.com/Nailan-Nobre" target="_blank" style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 20px; width: 100%;">
<img src="https://github.com/EtoDoze.png" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 2px solid #e0e0e0;"/>
<div>
<h3 style="margin: 0 0 5px 0; color: #333;">Roberto</h3>
</div>
</a>
</div>

##

## 📄 Licença

Este projeto está sob a licença MIT. Consulte o arquivo LICENSE para mais detalhes.
