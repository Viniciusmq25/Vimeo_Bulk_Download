# Vimeo Bulk Downloader

Este repositório contém um script em Python que faz o download em massa de todos os vídeos de uma conta do Vimeo. Ele percorre automaticamente todas as pastas ("Projects") e também os vídeos que não pertencem a nenhuma pasta, escolhe o melhor arquivo MP4 disponível para cada vídeo e salva um arquivo JSON com os metadados correspondentes.

## ✨ Recursos principais

- Autenticação via token pessoal do Vimeo.
- Paginação automática da API para cobrir todos os vídeos.
- Escolha do melhor arquivo disponível (progressivo ou download direto).
- Criação de estrutura de pastas espelhando os "Projects" do Vimeo.
- Retomada automática de downloads interrompidos (range requests).
- Geração de metadados em JSON ao lado de cada vídeo baixado.
- Opção `--overwrite` para forçar sobrescrita de arquivos existentes.

## 📋 Pré-requisitos

- Python 3.8 ou superior instalado.
- Token pessoal (Personal Access Token) do Vimeo com os escopos `public`, `private` e `video_files`.
- Dependências Python:
  - `requests`
  - `tqdm`
  - `tenacity`

Você pode instalá-las diretamente com:

```powershell
python -m pip install --upgrade pip
python -m pip install requests tqdm tenacity
```

> **Dica:** considere criar um ambiente virtual (`python -m venv .venv`) antes de instalar as dependências.

## 🔐 Configurando o token do Vimeo

1. Acesse [https://developer.vimeo.com/apps](https://developer.vimeo.com/apps) e crie um **Personal Access Token** com os escopos `public`, `private` e `video_files`.
2. Guarde o token gerado; ele será utilizado para autenticação nas chamadas da API.
3. Defina a variável de ambiente `VIMEO_TOKEN` para que o script possa usá-la automaticamente. Em um terminal PowerShell:

```powershell
# Somente para a sessão atual
$env:VIMEO_TOKEN = "seu_token_aqui"

# Opcional: persistir para todas as sessões futuras
setx VIMEO_TOKEN "seu_token_aqui"
```

## 🚀 Como executar

O script possui help integrado. Para consultá-lo:

```powershell
python vimeo_bulk_download.py --help
```

### Exemplo básico

Se a variável de ambiente `VIMEO_TOKEN` estiver configurada:

```powershell
python vimeo_bulk_download.py --out "D:\Backup\Vimeo"
```

### Informando o token pela linha de comando

```powershell
python vimeo_bulk_download.py --token "seu_token_aqui" --out "D:\Backup\Vimeo"
```

### Forçando sobrescrita de arquivos

```powershell
python vimeo_bulk_download.py --out "D:\Backup\Vimeo" --overwrite
```

#### Parâmetros disponíveis

- `--out PATH` (opcional): caminho de saída dos downloads. Se não informado, usa o caminho padrão configurado no script.
- `--token TOKEN` (opcional): token do Vimeo. Se omitido, o script tenta ler `VIMEO_TOKEN`.
- `--overwrite`: sobrescreve arquivos existentes com o mesmo nome.

## 🗂️ Estrutura de saída

- Cada pasta (Project) do Vimeo vira uma subpasta dentro do diretório escolhido.
- Vídeos fora de pastas vão direto para o diretório raiz de saída.
- Para cada vídeo baixado, um arquivo `nome_do_video.ext` e um `nome_do_video.ext.json` com os metadados são criados.

## 🧠 Comportamento e boas práticas

- **Paginação da API:** o script busca 50 itens por página (limite seguro da API) e segue até o fim.
- **Retentativas automáticas:** chamadas HTTP e downloads usam `tenacity` para repetir em caso de falha temporária ou *rate limiting* (`HTTP 429`).
- **Retomada de download:** se um arquivo parcial existir, o download continua de onde parou.
- **Seleção do melhor arquivo:** prioriza arquivos progressivos MP4 com maior resolução/bitrate. Caso não existam, usa o melhor link alternativo disponível.

## 🛠️ Solução de problemas

| Sintoma | Possível causa | Ação sugerida |
| --- | --- | --- |
| `Error: provide --token or set VIMEO_TOKEN` | Token não fornecido | Passe `--token` ou defina a variável `VIMEO_TOKEN`. |
| `401 Unauthorized` | Token inválido ou escopos insuficientes | Gere um token novo com os escopos corretos. |
| `Rate limited; retrying` | Muitas requisições em pouco tempo | Aguarde; o script respeita o `Retry-After` automaticamente. |
| Downloads que param no meio | Queda de conexão | O script retoma do ponto em que parou; apenas execute novamente. |
| Arquivos duplicados não sobrescritos | `--overwrite` não usado | Adicione `--overwrite` para forçar a substituição. |

## ✅ Checklist rápido antes de rodar

- [ ] Python 3.8+ instalado
- [ ] Dependências instaladas (`pip install requests tqdm tenacity`)
- [ ] Token do Vimeo com escopos `public`, `private`, `video_files`
- [ ] Variável `VIMEO_TOKEN` definida ou token passado por parâmetro
- [ ] Diretório de saída com espaço suficiente

## 📦 Estrutura do projeto

```
Vimeo_API/
├── vimeo_bulk_download.py   # Script principal
├── videos/                  # Pasta opcional para armazenar downloads
└── README.md                # Este arquivo
```

## 🧭 Próximos passos sugeridos

- Criar um arquivo `requirements.txt` para facilitar a instalação das dependências.
- Adicionar testes automatizados (por exemplo, mocks da API) para garantir a estabilidade.
- Embalar o script como CLI (`pipx`/`setuptools`) para distribuição mais simples.

## 📄 Licença

Nenhuma licença foi declarada neste repositório até o momento. Adicione uma licença ao seu critério se for distribuir o script.

## 🙋‍♂️ Suporte

Encontrou um problema ou tem uma sugestão? Abra uma *issue* descrevendo o cenário e, se possível, inclua trechos de logs exibidos no terminal.
