import telebot
import threading
import time
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime, timedelta
import pytz

# Configurações iniciais
API = IQ_Option("zezinhoplay83@gmail.com", "Cirlene2020")
API.connect()
bot = telebot.TeleBot('6173855534:AAEnFzb7vqTIDPuLMAl7Em_19IolY08nZt4')

# Variáveis globais
lista_sinais = []
sinais_passados = []
cancelar_execucao = False
adiantamento = 0
tipo = 'digital'
niveis_martingale = 1
conta = 'PRACTICE'

# Função para conectar na conta IQ Option
def conectar_conta():
    check, reason = API.connect()
    if check:
        print('Conectado com sucesso')
    else:
        if reason == '{"code":"invalid_credentials","message":"You entered the wrong credentials. Please ensure that your login/password is correct."}':
            print('Email ou senha incorreta')
        else:
            print('Houve um problema na conexão')
            print(reason)
    API.change_balance(conta)

# Função para buscar a hora do servidor da corretora
def horario_corretora():
    timestamp = API.get_server_timestamp()
    now = datetime.fromtimestamp(timestamp, pytz.utc)  # Hora em UTC
    now_sao_paulo = now.astimezone(pytz.timezone('America/Sao_Paulo'))
    return now_sao_paulo

# Função para abrir ordem e checar resultado
def compra(ativo, valor, direcao, exp, tipo):
    exp = int(exp)
    if tipo == 'digital':
        check, id = API.buy_digital_spot_v2(ativo, valor, direcao, exp)
    else:
        check, id = API.buy(valor, ativo, direcao, exp)

    if check:
        while True:
            time.sleep(0.5)
            status, resultado = API.check_win_digital_v2(id) if tipo == 'digital' else API.check_win_v4(id)
            if status:
                return resultado
    else:
        return None

# Função para agendar a ordem
def agendar_ordem(horario_entrada_str, ativo, valor, direcao, exp, tipo, chat_id):
    global cancelar_execucao
    agora = horario_corretora()
    horario_entrada = datetime.strptime(horario_entrada_str, '%H:%M:%S').time()
    horario_entrada_completo = datetime.combine(agora.date(), horario_entrada)
    horario_entrada_completo = pytz.timezone('America/Sao_Paulo').localize(horario_entrada_completo)
    tempo_espera = (horario_entrada_completo - agora).total_seconds()

    if tempo_espera < 0:
        sinais_passados.append((horario_entrada_str, ativo, valor, direcao, exp))
        return None

    message = bot.send_message(chat_id, f'Hora atual da corretora: {agora.strftime("%H:%M:%S")}. Esperando {tempo_espera:.2f} segundos para {ativo}...')

    while tempo_espera > 0:
        if cancelar_execucao:
            bot.send_message(chat_id, "Operação cancelada antes de ser executada.")
            return None
        time.sleep(1)
        agora = horario_corretora()
        tempo_espera = (horario_entrada_completo - agora).total_seconds()

        if tempo_espera > 0:
            bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=f'Hora atual da corretora: {agora.strftime("%H:%M:%S")}. Esperando {tempo_espera:.2f} segundos para {ativo}...')
        else:
            bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=f'Hora atual da corretora: {agora.strftime("%H:%M:%S")}. Iniciando ordem para {ativo}...')

    if not cancelar_execucao:
        resultado = compra(ativo, valor, direcao, exp, tipo)
        return resultado

# Função para aplicar a estratégia de Martingale automaticamente
def aplicar_martingale(ativo, valor_inicial, direcao, exp, tipo, niveis, horario_entrada_str, chat_id):
    global cancelar_execucao
    valor = valor_inicial
    nivel = 1

    while nivel <= niveis:
        if cancelar_execucao:
            bot.send_message(chat_id, "Estratégia de Martingale cancelada.")
            return None
        
        bot.send_message(chat_id, f'Tentando nível {nivel} com valor {valor} para {ativo}')
        resultado = agendar_ordem(horario_entrada_str, ativo, valor, direcao, exp, tipo, chat_id)

        if resultado is not None:
            if resultado > 0:
                bot.send_message(chat_id, f'Entrada vencedora com valor {valor} para {ativo}. Ciclo de Martingale encerrado.')
                break
            else:
                bot.send_message(chat_id, f'LOSS no nível {nivel} para {ativo}. Aplicando Martingale para o próximo nível.')
                valor *= 2
                nivel += 1
        else:
            bot.send_message(chat_id, f'Erro ao tentar abrir a ordem para {ativo}.')
            break

    if nivel > niveis:
        bot.send_message(chat_id, f'Número máximo de níveis de Martingale alcançado para {ativo}.')

# Função para processar o sinal
def processar_sinal(sinal, chat_id):
    horario_entrada_str, ativo, valor, direcao, exp = sinal.split(';')
    valor = float(valor)
    bot.send_message(chat_id, f'\n >> Entrada agendada para {horario_entrada_str} com adiantamento de {adiantamento} segundos para {ativo}')
    horario_entrada_corretora = datetime.strptime(horario_entrada_str, '%H:%M:%S') - timedelta(seconds=adiantamento)
    horario_entrada_corretora_str = horario_entrada_corretora.strftime('%H:%M:%S')

    aplicar_martingale(ativo, valor, direcao, exp, tipo, niveis_martingale, horario_entrada_corretora_str, chat_id)

# Comando /start
@bot.message_handler(commands=['start'])
def iniciar_operacao(session):
    global cancelar_execucao
    cancelar_execucao = False

    chat_id = session.chat.id

    bot.send_message(chat_id, 'Selecione a conta em que deseja conectar: demo ou real')
    bot.register_next_step_handler_by_chat_id(chat_id, selecionar_conta)

def selecionar_conta(session):
    global conta
    chat_id = session.chat.id
    escolha = session.text

    if escolha == 'demo':
        conta = 'PRACTICE'
        bot.send_message(chat_id, 'Conta demo selecionada')
    elif escolha == 'real':
        conta = 'REAL'
        bot.send_message(chat_id, 'Conta real selecionada')
    else:
        bot.send_message(chat_id, 'Escolha incorreta! Digite demo ou real')
        return
    conectar_conta()

    bot.send_message(chat_id, '\n >> Digite os sinais (separados por vírgula, formato HH:MM:SS;ativo;valor;call/put;expiração): ')
    bot.register_next_step_handler_by_chat_id(chat_id, configurar_operacao)

def configurar_operacao(session):
    global lista_sinais
    chat_id = session.chat.id
    sinais_input = session.text
    lista_sinais = sinais_input.split(',')

    bot.send_message(chat_id, '\n >> Quantos segundos de adiantamento? (1, 2 ou 3): ')
    bot.register_next_step_handler_by_chat_id(chat_id, definir_adiantamento)

def definir_adiantamento(session):
    global adiantamento
    chat_id = session.chat.id
    adiantamento = int(session.text)

    bot.send_message(chat_id, '\n >> digital ou binarias? ')
    bot.register_next_step_handler_by_chat_id(chat_id, definir_tipo)

def definir_tipo(session):
    global tipo
    chat_id = session.chat.id
    tipo = session.text

    bot.send_message(chat_id, '\n >> Quantos níveis de Martingale deseja aplicar? (1, 2 ou 3): ')
    bot.register_next_step_handler_by_chat_id(chat_id, definir_martingale)

def definir_martingale(session):
    global niveis_martingale
    chat_id = session.chat.id
    niveis_martingale = int(session.text)

    bot.send_message(chat_id, 'Configuração concluída. Use o comando /operar para iniciar as operações.')

@bot.message_handler(commands=['operar'])
def operar_lista(session):
    global cancelar_execucao
    cancelar_execucao = False
    chat_id = session.chat.id

    if not lista_sinais:
        bot.send_message(chat_id, 'Nenhum sinal configurado.')
        return

    if sinais_passados:
        bot.send_message(chat_id, 'Os seguintes sinais passaram da hora e não serão executados:')
        for sinal in sinais_passados:
            bot.send_message(chat_id, f'Horário: {sinal[0]} | Ativo: {sinal[1]} | Valor: {sinal[2]} | Direção: {sinal[3]} | Expiração: {sinal[4]}')
        sinais_passados.clear()

    bot.send_message(chat_id, 'Iniciando a execução dos sinais.')

    threads = []
    for sinal in lista_sinais:
        thread = threading.Thread(target=processar_sinal, args=(sinal, chat_id))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    bot.send_message(chat_id, 'Processamento concluído.')

@bot.message_handler(commands=['cancelar'])
def cancelar_operacao(session):
    global cancelar_execucao
    cancelar_execucao = True
    bot.send_message(session.chat.id, "Operações e configurações foram canceladas.")

bot.polling()
