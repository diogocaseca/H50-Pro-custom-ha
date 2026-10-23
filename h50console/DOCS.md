# H50 Console no Home Assistant

Painel completo para aspiradores Xiaomi **H50 Pro** (`xiaomi.vacuum.ov42gl`) dentro do Home Assistant: aparece na barra
lateral (**Aspirador**), usa o login e o HTTPS do próprio HA e conversa com o robô **pela rede local** (UDP 54321).
A nuvem Xiaomi só é necessária para baixar o **mapa** (o H50 Pro não entrega o mapa pela rede local) e para trazer o
token do robô automaticamente.

## Instalação

1. No Home Assistant: **Configurações → Apps → Loja de apps**.
2. Menu **⋮ → Repositórios**, adicione `https://github.com/diogocaseca/H50-Pro-custom-ha` e feche.
3. Procure **H50 Console** na loja, clique em **Instalar** e depois em **Iniciar**.
4. Ative **Mostrar na barra lateral**. O painel abre em **Aspirador**.

O app usa a **rede do host** (`host_network`): é o que permite achar o robô por broadcast e falar com ele em UDP 54321.
O robô e o Home Assistant precisam estar na **mesma rede** (mesma sub-rede/VLAN).

## Primeiro uso

1. Abra **Aspirador → Robôs**.
2. **Conectar a conta Xiaomi**: o painel mostra um QR code; escaneie com o app **Xiaomi Home** (serve também para contas
   Google/Apple). A sessão fica guardada no app; a senha da conta nunca passa por ele.
3. **Adicionar o robô pela conta**: o token vem sozinho, junto com o DID; o IP é achado na rede local pelo DID.
4. Em **Editar**, escolha **Como falar com o robô → Só rede local** (veja abaixo) e salve.
5. Volte ao **Início**: o mapa é baixado da nuvem na primeira abertura.

### Por que "Só rede local" (e não "Automático")

| Transporte | Comandos e leituras | Quando a rede local falha |
|---|---|---|
| **Só rede local** (recomendado aqui) | UDP 54321, direto com o robô | o painel mostra "sem resposta"; **nada** vai para a nuvem |
| Automático | rede local | **usa a nuvem Xiaomi de reserva**: comandos passam pelos servidores da Xiaomi |
| Só nuvem | nuvem Xiaomi | — |

Como o Home Assistant fica sempre em casa, não há motivo para a reserva pela nuvem. Com **Só rede local**, a conta Xiaomi
continua sendo usada apenas para: baixar o mapa, a lista de dispositivos/token ao cadastrar e, se você pedir, o
histórico de limpezas.

## Opções

| Opção | Padrão | O que faz |
|---|---|---|
| `password` | vazio | Senha para o **acesso direto** (`http://<ip-do-ha>:8050`). Não é usada pelo painel na barra lateral |
| `viewer_password` | vazio | Senha do perfil **somente leitura** no acesso direto (consulta, sem comandos) |
| `direct_access` | desligado | Liga o acesso direto pela porta 8050. Desligado, o app recusa qualquer conexão que não venha do HA |
| `cloud_region` | `auto` | Servidor da nuvem Xiaomi em que o robô está: `us` (EUA, onde costumam ficar as contas do Brasil), `de` (Europa), `sg` (Singapura), `cn` (China), `ru` (Rússia), `i2` (Índia). Veja abaixo |
| `log_level` | `info` | `debug`, `info`, `warning` ou `error` |

### Acesso direto (opcional)

Com a rede do host o Docker não consegue "fechar" a porta: a 8050 fica alcançável na sua rede local. Por isso o próprio app
recusa tudo o que não vem do Ingress enquanto `direct_access` estiver desligado.

Se ligar o acesso direto (por exemplo, para instalar o painel como app no celular ou usar o servidor MCP), defina `password`.
Sem ela, o painel pede uma senha nova com um **código de primeiro acesso** que aparece no **Registro** do app.
**Não** abra a porta 8050 do roteador para a internet; para acesso de fora use o próprio Home Assistant (Nabu Casa, VPN).

### Servidor da nuvem (`cloud_region`)

Em `auto`, o painel usa o primeiro servidor da Xiaomi em que a conta tem **algum** aparelho. Se a conta tem aparelhos em
servidores diferentes (por exemplo, lâmpadas no `us` e o robô no `de`), ele pode ficar no servidor errado: o mapa não
baixa e o robô não aparece em **Adicionar pela conta**. Nesse caso escolha o servidor do robô (é a região escolhida no
app Xiaomi Home quando o robô foi adicionado), salve e reinicie o app. O servidor em uso aparece em **Robôs**
("servidor …"). A opção só afeta a nuvem (mapa e cadastro); os comandos continuam pela rede local.

## Segurança

- Pelo Ingress, o HA já autenticou você: o painel entra direto como **administrador**. Só administradores do HA veem o painel.
  O app só confia nas conexões vindas do gateway do Ingress (`172.30.32.2`), conferindo o IP real da conexão.
- Qualquer outra origem continua exigindo senha, com os mesmos cabeçalhos de segurança do painel fora do HA.

## Dados e backup

Tudo fica em `/data` do app: tokens dos robôs, sessão da conta Xiaomi, bancos de histórico e mapas. Essa pasta entra nos
**backups do Home Assistant**; como ela contém tokens e a sessão da nuvem, prefira backups criptografados.
A aba **Manutenção** do painel também gera backups criptografados próprios.

## Problemas comuns

| Sintoma | Solução |
|---|---|
| O app não inicia: porta 8050 em uso | Outro serviço do host usa a 8050 (a rede do host compartilha as portas). Libere a porta |
| O robô não aparece na busca | Robô e HA em redes/VLANs diferentes, ou broadcast bloqueado. Informe o IP no cadastro e reserve o IP no roteador |
| "Sem resposta do robô" | O IP mudou? **Robôs → Achar pelo DID**. Confira se o transporte é "Só rede local" e se o robô está ligado |
| O mapa não aparece | A conta Xiaomi precisa estar conectada (**Robôs**). O mapa vem da nuvem; os comandos não. Se o robô está em outro servidor da Xiaomi, ajuste `cloud_region` |
| "acesso direto desligado" | Você abriu `http://<ip>:8050`. Use o painel pela barra lateral, ou ligue `direct_access` |

## De onde vem o código

O painel é o [H50 Console](https://github.com/nathanabreu/H50-Pro-custom), de
[Nathan Dame Abreu](https://github.com/nathanabreu). Este app não guarda uma cópia dele: ao instalar ou atualizar, o
Home Assistant baixa o original num commit fixo (`H50_COMMIT` em `build.yaml`) e aplica patches pequenos
(pasta `patches/`), todos opt-in: caminhos relativos no front, redirecionamento relativo para o login, o modo Ingress
e a escolha do servidor da nuvem.
Se um patch não aplicar, a instalação falha em vez de gerar um painel incompleto. Detalhes no
[repositório do app](https://github.com/diogocaseca/H50-Pro-custom-ha).

## Licença

MIT. Baseado em [nathanabreu/H50-Pro-custom](https://github.com/nathanabreu/H50-Pro-custom).
