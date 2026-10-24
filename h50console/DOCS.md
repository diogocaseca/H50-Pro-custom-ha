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
| `admins` | vazio | Logins de usuários do HA que entram como **administrador** no painel, além dos administradores do HA. Veja [Quem pode fazer o quê](#quem-pode-fazer-o-quê) |
| `others` | `operator` | Perfil dos demais usuários do HA: `operator` (comanda o robô sem mexer em configurações) ou `viewer` (só consulta) |
| `zone_limit` | `3` | Quantas zonas dá para desenhar no mapa por limpeza (e salvar numa zona com nome), de 1 a 10. Rotinas do app Xiaomi Home e zonas já salvas não são afetadas |
| `mqtt` | desligado | Integração MQTT: cria o robô como dispositivo do HA. Veja [Integração MQTT](#integração-mqtt-robô-como-dispositivo-do-ha) |
| `mqtt_host` | vazio | Endereço do broker. Vazio = app Mosquitto broker do HA. Só para broker externo |
| `mqtt_port` | `1883` | Porta do broker |
| `mqtt_user` / `mqtt_password` | vazio | Usuário e senha do broker. Vazio = o app tenta o usuário que o Supervisor fornece |
| `mqtt_discovery_prefix` | `homeassistant` | Prefixo do MQTT discovery. Só mude se alterou na integração MQTT do HA |
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

## Quem pode fazer o quê

O painel aparece na barra lateral de **todos** os usuários do Home Assistant. O perfil de cada um vem do usuário do HA:

| Perfil | Quem | O que pode |
|---|---|---|
| Administrador | Administradores do HA e os logins listados em `admins` | Tudo |
| Operador (`others: operator`, padrão) | Os demais usuários do HA | Ver tudo o que o somente leitura vê; iniciar, pausar, continuar, parar, voltar à base, localizar, limpar cômodos, zonas (desenhadas na hora ou salvas) e rotinas, as funções da base (esvaziar pó, lavar e secar o mop) e escolher os modos da limpeza no **Início** (modo, sucção, água, caminho, passadas, atalho) |
| Somente leitura (`others: viewer`) | Os demais usuários do HA | Só consultar |

O operador **não** mexe na aba **Ajustes** nem nas configurações da estação, não cadastra nem remove robôs, não mexe na
conta Xiaomi, em senhas, backups, notificações, edição do mapa, zonas salvas (salvar e apagar), consumíveis (zerar) nem
no laboratório.

**Como o painel sabe quem é admin:** o Supervisor informa o usuário do HA em cada pedido. As versões mais novas do
Supervisor também informam o grupo (administrador ou não); nas mais antigas, só o login. Por isso existe a opção `admins`:
**inclua o seu login** (o nome de usuário com que você entra no HA, não o nome de exibição), por exemplo:

```yaml
admins:
  - joao
```

Se não souber o login, abra o painel e veja o **Registro** do app: aparece
`Ingress: usuário 'joao' do Home Assistant entrou como operador`. Na aba **Configurações** do painel o mesmo aviso mostra o
usuário com que você entrou.

## Limpeza por zona

No **Início**, toque em **Desenhar zona** (abaixo do mapa) e arraste no mapa para fazer um retângulo. Dá para desenhar
até 3 zonas (opção `zone_limit`, até 10); cada uma aparece numerada, com o tamanho em metros, e o **✕** tira uma
delas. Toque em **Concluir** e depois em **Iniciar limpeza**. A limpeza usa os **Modos** atuais. O mapa vem da nuvem,
então desenhar zonas exige a conta Xiaomi conectada; a limpeza em si vai pela rede local.

- Cada lado precisa ter ao menos 0,3 m. Abaixo de 0,7 m o painel avisa: o robô pode recusar zonas pequenas.
- Zonas e cômodos não se misturam: escolher um cômodo desfaz as zonas e vice-versa.
- **Zoom:** botões **+**, **−** e **⟲** no canto do mapa, pinça com dois dedos ou **Ctrl + rodinha**. Com zoom,
  arrastar move o mapa; no modo "Desenhar zona", um dedo desenha e dois movem e ampliam.

**Zonas com nome** (só o administrador salva e apaga): depois de desenhar, **Salvar zona** pede um nome. As zonas salvas
aparecem no menu **Área**, junto dos cômodos, para todos que podem comandar o robô. O nome não pode repetir o de outra
zona nem o de uma rotina do app Xiaomi Home. Para apagar, use o 🗑 no menu **Área**.

## Rotinas personalizadas

As rotinas criadas no app Xiaomi Home aparecem no **Início** (▶). O painel ainda não sabe disparar a rotina do jeito
do app; ele limpa os **cômodos** (ou as **zonas**) da rotina e, antes, ajusta o **Modo de limpeza** para o da rotina
(só aspirar, aspirar e esfregar...). Por isso:

- depois da rotina, o Modo de limpeza fica como a rotina deixou;
- sucção, água, passadas e caminho são os atuais (a rotina não informa esses ajustes ao robô);
- **rotina por zonas:** a lista de rotinas não traz as zonas. O painel as aprende quando a rotina roda pelo app Xiaomi
  Home (inclusive por agendamento do app), com o app H50 Console ligado. Até lá, o ▶ fica desabilitado com o aviso
  "rode uma vez pelo app Xiaomi Home para o painel aprender as zonas". Se você mudar as zonas no app, o painel pega as
  novas na próxima vez que a rotina rodar;
- rotina com modos diferentes por cômodo (ex.: aspira a sala e passa pano na cozinha) não roda pelo painel: o ▶ fica
  desabilitado e o motivo aparece embaixo do nome. Use o app Xiaomi Home.

## Integração MQTT (robô como dispositivo do HA)

Com a opção `mqtt` ligada, cada robô cadastrado no painel vira um **dispositivo** no Home Assistant (MQTT discovery):
dá para usar o card de aspirador, ver bateria e consumíveis em qualquer dashboard e criar automações.

**Requisitos:** o app **Mosquitto broker** instalado e a integração **MQTT** configurada no HA.

**Usuário e senha do broker:** preencha `mqtt_user` e `mqtt_password` com um usuário do Home Assistant (o Mosquitto do HA
aceita os usuários do HA; vale criar um só para isso, sem acesso de administrador) ou com um login configurado nas
opções do app Mosquitto. Em branco, o app tenta o usuário que o Supervisor fornece aos apps. `mqtt_port` já vem com a
porta padrão (1883). `mqtt_host` fica em branco para o Mosquitto do HA: o app usa a rede do host e chega ao broker por
`127.0.0.1`.

**Como ligar:** aba **Configuração** do app → **Integração MQTT** → ligar → **Salvar** → reiniciar o app. O robô aparece
em **Configurações → Dispositivos e serviços → MQTT**.

**Continua 100% local:** o HA fala com o broker, o broker com o app, e o app com o robô pela rede local. Os comandos
passam pelo painel, então valem os mesmos bloqueios ("não dá para iniciar agora"), a fila de prioridade e o registro de
comandos da aba **Diagnóstico**.

### Entidades

| Entidade | O que é |
|---|---|
| Aspirador (`vacuum`) | Estado (limpando, na base, pausado, voltando, parado, erro), iniciar/continuar, pausar, parar, voltar à base, localizar, limpeza pontual, potência de sucção e limpeza por cômodo |
| Bateria, Status, Progresso da limpeza, Área limpa, Tempo de limpeza, Progresso da secagem, Secagem restante, Falha | Sensores. Progresso da secagem: % da secagem dos mops na base; Secagem restante: minutos que faltam (os dois ficam em 0 quando não está secando) |
| Carregando, Tanque de água suja cheio, Tanque de água limpa vazio | Sensores binários |
| Limpeza em andamento | Sensor binário: **ligado** do início ao fim da limpeza, inclusive pausas e idas à base no meio dela (lavar o mop, recarregar para continuar); **desliga** quando o robô volta à base no fim, ou ao parar ou mandar voltar |
| Conectado pela rede local | Diagnóstico: se o painel está conseguindo falar com o robô |
| Escova principal, Escova lateral, Filtro, Mop, Saco de pó | Diagnóstico: vida útil em % |
| Potência de sucção, Modo de limpeza, Nível de água do mop, Caminho, Tempos de limpeza | Seletores (configuração) |
| Esvaziar o pó, Lavar o mop, Secar o mop, Parar a lavagem, Parar a secagem, Autolimpeza da base | Botões |
| Rotina: …, Zona: … | Botões: um por rotina que o painel consegue rodar e um por zona salva. Aparecem, mudam e somem sozinhos (zonas na hora; rotinas criadas no app em até ~5 min) |

Se o painel não conseguir falar com o robô, as entidades dele ficam **indisponíveis** (o painel leva até ~1 min para
perceber, conforme o intervalo de leitura). Se o app parar, todas ficam indisponíveis.

### Cômodos

Os cômodos vêm do mapa (é preciso a conta Xiaomi conectada e o mapa baixado pelo menos uma vez). Eles aparecem como
**segmentos** do aspirador: nas versões do HA com limpeza por área, associe cada cômodo a uma área do HA. Também dá para
pedir pelo `vacuum.send_command` (o `id` do cômodo aparece no atributo `segments` do aspirador):

```yaml
action: vacuum.send_command
target:
  entity_id: vacuum.robo_da_sala
data:
  command: clean_rooms
  params:
    rooms: [3, 5]
```

Zonas: `clean_zones` com `zone` (nome de uma zona salva, ex.: `params: {zone: Frente do sofá}`) ou `zones` (retângulos
`[x1, y1, x2, y2]` em mm, nas coordenadas do mapa).

Outros comandos: `custom` com `id` (uma rotina do app Xiaomi Home, ex.: `params: {id: 2}`) ou uma ação simples
(`sweep`, `mop`, `sweep-mop`, `sweep-then-mop`, `dust`, `wash-mop`, `dry`, `charge`...), sem `params`.

### Exemplos

Card de aspirador no dashboard:

```yaml
type: tile
entity: vacuum.robo_da_sala
features:
  - type: vacuum-commands
    commands: [start_pause, stop, return_home, locate]
```

Avisar quando o tanque de água suja encher:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.robo_da_sala_tanque_de_agua_suja_cheio
    to: "on"
actions:
  - action: notify.notify
    data:
      message: Esvazie o tanque de água suja do robô.
```

Avisar quando a limpeza terminar:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.robo_da_sala_limpeza_em_andamento
    from: "on"
    to: "off"
actions:
  - action: notify.notify
    data:
      message: O robô terminou a limpeza.
```

Os nomes das entidades dependem do nome do robô no painel; confira em **Configurações → Entidades**.

**Atenção:** comandos vindos do HA (automações, cards, voz) **não pedem a confirmação** que o painel pede antes de tirar o
robô da base. Revise as automações que iniciam limpeza.

O **Registro** do app mostra o broker e o usuário em uso (`ponte MQTT: broker 127.0.0.1:1883, usuário ...`) e, se der
errado, o motivo: "não consegui conectar" (host ou porta) ou "broker recusou a conexão: Not authorized" (usuário ou
senha). A ponte tenta de novo sozinha, e o painel continua funcionando normalmente. Ao remover um robô no painel, o dispositivo sai do HA.

## Segurança

- Pelo Ingress, o HA já autenticou você: o painel entra direto, sem senha, com o perfil do seu usuário do HA (veja
  [Quem pode fazer o quê](#quem-pode-fazer-o-quê)). Os perfis são aplicados pelo servidor do painel, não só escondidos na tela.
- O usuário só é aceito vindo do gateway do Ingress, e um cabeçalho de usuário repetido (sinal de tentativa de forjar)
  nunca dá acesso de administrador. Mantenha o Supervisor atualizado: as versões novas reforçam essa proteção.
  O app só confia nas conexões vindas do gateway do Ingress (`172.30.32.2`), conferindo o IP real da conexão.
- Qualquer outra origem continua exigindo senha, com os mesmos cabeçalhos de segurança do painel fora do HA.
- Com a integração MQTT ligada, a ponte conversa com o painel por `127.0.0.1` com um token aleatório gerado a cada
  início (nunca gravado). O token só vale vindo do próprio app: da rede, nem com ele o painel abre.
- Quem consegue publicar no seu broker MQTT consegue comandar o robô: mantenha o Mosquitto com usuário e senha (o padrão
  do app Mosquitto do HA).

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
| Rotina "só aspirar" saiu com pano (até 0.3.4) | Atualize o app: desde a 0.3.5 o modo da rotina é ajustado antes de limpar |
| "acesso direto desligado" | Você abriu `http://<ip>:8050`. Use o painel pela barra lateral, ou ligue `direct_access` |

## De onde vem o código

O painel é o [H50 Console](https://github.com/nathanabreu/H50-Pro-custom), de
[Nathan Dame Abreu](https://github.com/nathanabreu). Este app não guarda uma cópia dele: ao instalar ou atualizar, o
Home Assistant baixa o original num commit fixo (`H50_COMMIT` em `build.yaml`) e aplica patches pequenos
(pasta `patches/`), todos opt-in: caminhos relativos no front, redirecionamento relativo para o login, o modo Ingress
a escolha do servidor da nuvem, a API local por token usada pela integração MQTT e os perfis por usuário do HA. A ponte MQTT é código deste app.
Se um patch não aplicar, a instalação falha em vez de gerar um painel incompleto. Detalhes no
[repositório do app](https://github.com/diogocaseca/H50-Pro-custom-ha).

## Licença

MIT. Baseado em [nathanabreu/H50-Pro-custom](https://github.com/nathanabreu/H50-Pro-custom).
