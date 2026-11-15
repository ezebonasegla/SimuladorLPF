# Actualizar los resultados desde la VPS

`scripts/actualizar.sh` baja los resultados de promiedos y, si cambió algo,
sube `resultados.json` al repo. Netlify y Vercel se republican solos con cada push.

Se configura una sola vez. Conectate por SSH a la VPS y seguí estos pasos.

## 1. Requisitos

```bash
sudo apt-get update && sudo apt-get install -y git python3
```

## 2. Llave para que la VPS pueda subir al repo

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/simuladorlpf -C "vps simuladorlpf"
cat ~/.ssh/simuladorlpf.pub
```

Copiá lo que muestra el `cat` y agregalo en GitHub:
**repo SimuladorLPF → Settings → Deploy keys → Add deploy key**, pegá la llave y **tildá "Allow write access"**.

Después, para que git use esa llave:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-simuladorlpf
  HostName github.com
  User git
  IdentityFile ~/.ssh/simuladorlpf
  IdentitiesOnly yes
EOF
ssh -o StrictHostKeyChecking=accept-new -T github-simuladorlpf   # tiene que decir "successfully authenticated"
```

## 3. Clonar el repo (clon dedicado, no lo uses para editar a mano)

```bash
git clone -b claude/simulador-clausura-2026 git@github-simuladorlpf:ezebonasegla/SimuladorLPF.git ~/simuladorlpf
chmod +x ~/simuladorlpf/scripts/actualizar.sh
~/simuladorlpf/scripts/actualizar.sh && echo OK   # prueba a mano
```

## 4. Programarlo cada 3 minutos

```bash
( crontab -l 2>/dev/null; echo '*/3 * * * * $HOME/simuladorlpf/scripts/actualizar.sh >> $HOME/simuladorlpf.log 2>&1' ) | crontab -
```

Para ver qué va haciendo: `tail -f ~/simuladorlpf.log` (si no hay cambios no escribe nada).

## Para frenarlo

```bash
crontab -l | grep -v simuladorlpf | crontab -
```
