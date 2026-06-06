# Backup e recuperação do banco

O código vive no GitHub, mas **todos os dados** (notícias, transcrições, texto
completo, resumos, assinantes do boletim, classificações) ficam apenas no MySQL
do Railway. Este guia descreve como fazer backup desses dados e como restaurá-los
em outra hospedagem.

> Os backups gerados ficam na pasta `backups/`, que está no `.gitignore` (nunca
> são enviados ao GitHub). Guarde-os em local seguro (Drive, outro disco, etc.).

---

## Método 1 — Sem expor o banco (recomendado): via `railway ssh`

O contêiner do Railway alcança o banco interno. O script `scripts/backup_db.py`
gera um dump SQL usando só `pymysql` (não precisa do cliente `mysqldump`).

```bash
mkdir -p backups
railway ssh --service coletor -- python scripts/backup_db.py \
    | gzip > backups/observatorio_$(date +%Y%m%d_%H%M%S).sql.gz
```

Pré-requisitos (uma vez): ter uma chave SSH registrada no Railway
(`railway ssh keys add -k minha-chave`, que lê a chave do ssh-agent) e
`StrictHostKeyChecking accept-new` no `~/.ssh/config` (gateway `ssh.railway.com`).

---

## Método 2 — Com proxy TCP público: via `mysqldump`

Mais simples de automatizar (cron), mas expõe o banco na internet.

1. No painel do Railway, abra o serviço **MySQL → Settings → Networking** e
   habilite o **TCP Proxy**. O Railway fornece um host e porta públicos
   (ex.: `gondola.proxy.rlwy.net:54321`) e a variável `MYSQL_PUBLIC_URL`.
2. Rode o script com a URL pública:

```bash
./scripts/backup_db.sh "mysql://root:SENHA@gondola.proxy.rlwy.net:54321/railway"
# ou
export BACKUP_DATABASE_URL="mysql://root:SENHA@HOST:PORTA/railway"
./scripts/backup_db.sh
```

Gera `backups/observatorio_AAAAMMDD_HHMMSS.sql.gz` e mantém os últimos
`KEEP` backups (padrão 14; ajuste com `KEEP=30 ./scripts/backup_db.sh ...`).

### Automatizar (cron diário às 3h)

```cron
0 3 * * * cd /caminho/observatorio-manaus && BACKUP_DATABASE_URL="mysql://..." ./scripts/backup_db.sh >> backups/backup.log 2>&1
```

---

## Enviar os backups para o Google Drive (rclone)

Os dumps em `backups/` ficam só na máquina local. Para guardá-los na nuvem,
use o `rclone` (já configurado com o remote `gdrive`, escopo `drive.file`,
que só enxerga arquivos criados pelo próprio rclone).

Enviar todos os backups locais para o Drive:

```bash
./scripts/upload_backups.sh
```

Isso usa `rclone copy` (nunca apaga nada no Drive) e manda os arquivos para
a pasta `gdrive:Backups-Observatorio`. Para outro remote/pasta:

```bash
RCLONE_REMOTE="gdrive:OutraPasta" ./scripts/upload_backups.sh
```

O `backup_db.sh` (Método 2) também envia automaticamente para o Drive se
`RCLONE_REMOTE` estiver definido:

```bash
RCLONE_REMOTE="gdrive:Backups-Observatorio" \
    BACKUP_DATABASE_URL="mysql://..." ./scripts/backup_db.sh
```

> Reconfigurar o rclone em outra máquina: instale o rclone e rode
> `rclone config create gdrive drive scope drive.file` (faz login no Google
> pelo navegador). O token fica em `~/.config/rclone/rclone.conf` — é secreto.

---

## Restaurar em outra hospedagem (recuperação de desastre)

1. Clone o repositório:
   ```bash
   git clone https://github.com/tmelo-uea/observatorio-manaus.git
   cd observatorio-manaus
   ```
2. Crie um banco MySQL novo (Railway, PlanetScale, VPS, etc.).
3. Restaure o dump mais recente:
   ```bash
   gunzip < backups/observatorio_AAAAMMDD_HHMMSS.sql.gz \
       | mysql -h NOVO_HOST -P PORTA -u USUARIO -p NOME_DO_BANCO
   ```
4. Copie `.env.example` para `.env` e preencha as credenciais (banco + chaves
   de API: `OPENAI_API_KEY`, `GROQ_API_KEY`, SendGrid/Brevo, etc.).
5. Suba os dois processos (ver `Procfile`):
   - web: `streamlit run "dashboard/0_Visão_Geral.py"`
   - worker: `python collector/runner.py`

O esquema do banco se recria sozinho no boot, mas restaurar o dump traz de volta
todo o histórico coletado.
