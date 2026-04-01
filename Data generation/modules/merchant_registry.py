import random
import numpy as np
import pandas as pd

CITY_ADDRESS_REFERENCES = [
    {
        'city': 'Sao Paulo',
        'uf': 'SP',
        'streets': ['Avenida Paulista', 'Rua da Consolacao', 'Rua Oscar Freire'],
        'neighborhoods': ['Bela Vista', 'Consolacao', 'Jardins'],
        'cep_prefixes': ['010', '013', '014']
    },
    {
        'city': 'Rio de Janeiro',
        'uf': 'RJ',
        'streets': ['Avenida Rio Branco', 'Avenida Atlantica', 'Rua Voluntarios da Patria'],
        'neighborhoods': ['Centro', 'Copacabana', 'Botafogo'],
        'cep_prefixes': ['200', '220', '222']
    },
    {
        'city': 'Belo Horizonte',
        'uf': 'MG',
        'streets': ['Avenida Afonso Pena', 'Rua da Bahia', 'Avenida do Contorno'],
        'neighborhoods': ['Centro', 'Savassi', 'Funcionarios'],
        'cep_prefixes': ['301', '303', '304']
    },
    {
        'city': 'Curitiba',
        'uf': 'PR',
        'streets': ['Rua XV de Novembro', 'Avenida Sete de Setembro', 'Avenida Republica Argentina'],
        'neighborhoods': ['Centro', 'Reboucas', 'Agua Verde'],
        'cep_prefixes': ['800', '802', '803']
    },
    {
        'city': 'Porto Alegre',
        'uf': 'RS',
        'streets': ['Avenida Borges de Medeiros', 'Rua dos Andradas', 'Avenida Ipiranga'],
        'neighborhoods': ['Centro Historico', 'Praia de Belas', 'Menino Deus'],
        'cep_prefixes': ['900', '901', '904']
    },
    {
        'city': 'Salvador',
        'uf': 'BA',
        'streets': ['Avenida Tancredo Neves', 'Avenida Sete de Setembro', 'Avenida ACM'],
        'neighborhoods': ['Caminho das Arvores', 'Dois de Julho', 'Iguatemi'],
        'cep_prefixes': ['400', '401', '418']
    },
    {
        'city': 'Recife',
        'uf': 'PE',
        'streets': ['Avenida Boa Viagem', 'Rua do Bom Jesus', 'Avenida Conde da Boa Vista'],
        'neighborhoods': ['Boa Viagem', 'Recife', 'Santo Amaro'],
        'cep_prefixes': ['500', '510', '520']
    },
    {
        'city': 'Fortaleza',
        'uf': 'CE',
        'streets': ['Avenida Beira Mar', 'Avenida Dom Luis', 'Avenida Washington Soares'],
        'neighborhoods': ['Meireles', 'Aldeota', 'Coco'],
        'cep_prefixes': ['600', '601', '608']
    },
    {
        'city': 'Brasilia',
        'uf': 'DF',
        'streets': ['SCS Quadra 08 Bloco B', 'SHN Quadra 5 Bloco A', 'CLS 306 Bloco C'],
        'neighborhoods': ['Asa Sul', 'Asa Norte', 'Sudoeste'],
        'cep_prefixes': ['700', '707', '706']
    },
    {
        'city': 'Goiania',
        'uf': 'GO',
        'streets': ['Avenida 85', 'Avenida T-63', 'Rua 9'],
        'neighborhoods': ['Setor Marista', 'Setor Bueno', 'Centro'],
        'cep_prefixes': ['740', '741', '742']
    },
    {
        'city': 'Vitoria',
        'uf': 'ES',
        'streets': ['Avenida Nossa Senhora da Penha', 'Avenida Jeronimo Monteiro', 'Rua Aleixo Netto'],
        'neighborhoods': ['Santa Lucia', 'Praia do Canto', 'Centro'],
        'cep_prefixes': ['290', '291', '292']
    },
    {
        'city': 'Florianopolis',
        'uf': 'SC',
        'streets': ['Avenida Beira Mar Norte', 'Rua Bocaiuva', 'Avenida Mauro Ramos'],
        'neighborhoods': ['Centro', 'Trindade', 'Agronomica'],
        'cep_prefixes': ['880', '881', '882']
    },
    {
        'city': 'Belem',
        'uf': 'PA',
        'streets': ['Avenida Presidente Vargas', 'Avenida Nazare', 'Travessa Padre Eutiquio'],
        'neighborhoods': ['Campina', 'Nazare', 'Umarizal'],
        'cep_prefixes': ['660', '661', '666']
    },
    {
        'city': 'Manaus',
        'uf': 'AM',
        'streets': ['Avenida Djalma Batista', 'Avenida Eduardo Ribeiro', 'Avenida Constantino Nery'],
        'neighborhoods': ['Chapada', 'Centro', 'Flores'],
        'cep_prefixes': ['690', '691', '692']
    },
    {
        'city': 'Cuiaba',
        'uf': 'MT',
        'streets': ['Avenida Getulio Vargas', 'Avenida Isaac Povoas', 'Avenida Historiador Rubens de Mendonca'],
        'neighborhoods': ['Centro Norte', 'Popular', 'Bosque da Saude'],
        'cep_prefixes': ['780', '781', '782']
    },
    {
        'city': 'Campo Grande',
        'uf': 'MS',
        'streets': ['Avenida Afonso Pena', 'Rua 14 de Julho', 'Avenida Mato Grosso'],
        'neighborhoods': ['Centro', 'Jardim dos Estados', 'Santa Fe'],
        'cep_prefixes': ['790', '791', '792']
    },
    {
        'city': 'Maceio',
        'uf': 'AL',
        'streets': ['Avenida Alvaro Otacilio', 'Avenida Fernandes Lima', 'Rua Deputado Jose Lages'],
        'neighborhoods': ['Jatiuca', 'Farol', 'Ponta Verde'],
        'cep_prefixes': ['570', '571', '572']
    },
    {
        'city': 'Joao Pessoa',
        'uf': 'PB',
        'streets': ['Avenida Epitacio Pessoa', 'Avenida Rui Carneiro', 'Rua Bancario Sergio Guerra'],
        'neighborhoods': ['Torre', 'Manaira', 'Bancarios'],
        'cep_prefixes': ['580', '581', '582']
    },
    {
        'city': 'Natal',
        'uf': 'RN',
        'streets': ['Avenida Engenheiro Roberto Freire', 'Avenida Salgado Filho', 'Avenida Prudente de Morais'],
        'neighborhoods': ['Ponta Negra', 'Lagoa Nova', 'Petropolis'],
        'cep_prefixes': ['590', '591', '592']
    },
    {
        'city': 'Aracaju',
        'uf': 'SE',
        'streets': ['Avenida Beira Mar', 'Avenida Adelia Franco', 'Rua Laranjeiras'],
        'neighborhoods': ['13 de Julho', 'Jardins', 'Centro'],
        'cep_prefixes': ['490', '491', '492']
    },
    {
        'city': 'Palmas',
        'uf': 'TO',
        'streets': ['Avenida JK', 'Avenida Teotonio Segurado', 'Quadra 104 Sul Alameda 12'],
        'neighborhoods': ['Plano Diretor Sul', 'Plano Diretor Norte', 'Taquaralto'],
        'cep_prefixes': ['770', '771', '772']
    },
    {
        'city': 'Sao Luis',
        'uf': 'MA',
        'streets': ['Avenida dos Holandeses', 'Avenida Colares Moreira', 'Rua Grande'],
        'neighborhoods': ['Ponta d Areia', 'Renascenca', 'Centro'],
        'cep_prefixes': ['650', '651', '652']
    },
    {
        'city': 'Teresina',
        'uf': 'PI',
        'streets': ['Avenida Frei Serafim', 'Avenida Joao XXIII', 'Avenida Raul Lopes'],
        'neighborhoods': ['Centro', 'Jockey', 'Noivos'],
        'cep_prefixes': ['640', '641', '642']
    },
    {
        'city': 'Porto Velho',
        'uf': 'RO',
        'streets': ['Avenida Sete de Setembro', 'Avenida Carlos Gomes', 'Rua Jose de Alencar'],
        'neighborhoods': ['Centro', 'Embratel', 'Olaria'],
        'cep_prefixes': ['768', '769', '789']
    },
    {
        'city': 'Rio Branco',
        'uf': 'AC',
        'streets': ['Avenida Ceara', 'Via Chico Mendes', 'Rua Benjamin Constant'],
        'neighborhoods': ['Centro', 'Bosque', 'Estacao Experimental'],
        'cep_prefixes': ['699', '698', '697']
    }
]

MCC_CODES = ['5411', '5812', '5541', '5732', '7995', '5999']


def generate_valid_cep(prefixes=None):
    """Generates a CEP in a valid Brazilian format (NNNNN-NNN)."""
    if not prefixes:
        prefixes = ['010', '013', '014', '020', '030', '200', '220', '300', '400', '500', '600', '700', '800', '900']

    prefix = random.choice(prefixes)
    middle = random.randint(0, 99)
    suffix = random.randint(0, 999)
    return f"{prefix}{middle:02d}-{suffix:03d}"


def build_random_full_address(city_ref):
    street = random.choice(city_ref['streets'])
    neighborhood = random.choice(city_ref['neighborhoods'])
    number = random.randint(10, 2500)
    cep = generate_valid_cep(city_ref['cep_prefixes'])
    return f"{street}, {number} - {neighborhood}, {city_ref['city']} - {city_ref['uf']}, {cep}, Brasil"


def generate_merchant_registry(merchant_ids_pool, num_merchants, fake):
    df_merch = pd.DataFrame()
    df_merch['merchant_id'] = merchant_ids_pool
    df_merch['merchant_name'] = [fake.company() for _ in range(num_merchants)]
    df_merch['mcc_code'] = np.random.choice(MCC_CODES, num_merchants)

    city_refs = random.choices(CITY_ADDRESS_REFERENCES, k=num_merchants)
    df_merch['merchant_city'] = [entry['city'] for entry in city_refs]
    df_merch['merchant_full_address'] = [build_random_full_address(entry) for entry in city_refs]

    return df_merch
