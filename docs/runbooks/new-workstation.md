# New workstation

## Ubuntu VM

```console
git clone https://github.com/tullas/vss.git
cd vss
./scripts/bootstrap-host.sh
vss secrets init --environment development
vss platform up --environment development
vss platform verify --environment development
```

## Ubuntu under WSL

```console
git clone https://github.com/tullas/vss.git
cd vss
./scripts/bootstrap-host.sh
./scripts/bootstrap-host.sh --resume
vss secrets init --environment development
vss platform up --environment development
vss platform verify --environment development
```

When bootstrap reports `RESTART_REQUIRED`, run exactly the printed PowerShell command before `--resume`.
When prompted during bootstrap, enter the sudo password directly into sudo.
The dedicated playbook then runs through that single authenticated boundary;
no Ansible password prompt or nested sudo is part of this supported path.

## Docker Desktop already integrated with WSL

```console
./scripts/bootstrap-host.sh
vss secrets init --environment development
vss platform up --environment development
vss platform verify --environment development
```

An accessible Docker Desktop daemon is reused; VSS does not install or manage Docker Desktop.

## Docker Engine inside WSL

```console
./scripts/bootstrap-host.sh
./scripts/bootstrap-host.sh --resume
vss secrets init --environment development
vss platform up --environment development
vss platform verify --environment development
```

## Restart-required recovery

From Windows PowerShell:

```powershell
wsl --shutdown
```

Back in Ubuntu:

```console
cd vss
./scripts/bootstrap-host.sh --resume
```

## Complete platform teardown

```console
vss platform down --environment development --yes
vss platform status --environment development
```

## Troubleshooting

Use these only to diagnose a failed supported command:

```console
ansible-playbook --syntax-check -i ansible/inventories/development/hosts.yml ansible/playbooks/bootstrap-local.yml
docker info
tofu -chdir=infrastructure/environments/development/local validate
```
