# **📊 Plano de Análises SQL & Módulo SQL Lab (Atualizado)**

**Documento de Arquitetura, Diagnóstico de Dados e Guia Técnico**

**Foco:** Análises Avançadas em SQL Nativo, Linhagem de Dados, Governança de Inputs e Tratamento de Schema

**Projeto:** Futebol Analytics & Match Simulator (futebol.db)

## **🎯 Visão Geral**

O **SQL Analytics Lab** disponibiliza uma suíte de consultas SQL nativas executadas diretamente sobre o banco relacional SQLite (futebol.db).

Do ponto de vista de **Governança de Dados, Data Quality e Engenharia de Machine Learning**, a validação via SQL garante a integridade dos inputs alimentados nos modelos de simulação (como a Regressão de Poisson para expectativa de gols e a predição de drift de desempenho).

> **Nota de compatibilidade de Schema:** As queries do plano foram ajustadas para lidar com colunas dinâmicas do banco (league\_name ou league), tratar compatibilidade de tipos (rating\_global ou overall) e mitigar erros clássicos de agrupamento com GROUP\_CONCAT em dialeto SQLite.

## **🗄️ Esquema Relacional do Banco de Dados (futebol.db)**

┌─────────────────────────────────┐       ┌─────────────────────────────────┐  
│             teams               │       │             players             │  
├─────────────────────────────────┤       ├─────────────────────────────────┤  
│ id (PK)             INTEGER     │1     N│ id (PK)             INTEGER     │  
│ name                TEXT        ├───────┤ team\_id (FK)        INTEGER     │  
│ league\_name / league TEXT       │       │ name                TEXT        │  
└─────────────────────────────────┘       │ position            TEXT        │  
                                          │ nationality         TEXT        │  
                                          │ date\_of\_birth       TEXT        │  
                                          │ rating\_global/overall REAL      │  
                                          └─────────────────────────────────┘

## **💻 Suíte de Consultas SQL e Conceitos Aplicados**

### **1\. Top 5 Atletas por Posição em Cada Liga (Window Functions)**

* **Conceitos:** DENSE\_RANK() OVER (PARTITION BY ... ORDER BY ...), CTEs (WITH), tratamento com COALESCE.  
* **Objetivo de Negócio:** Identificar os melhores talentos por setor tático em cada liga competitiva.  
* **Relevância para Governança:** Identifica distorções em ratings de ponta por posição antes da ingestão no simulador.

WITH RankedPlayers AS (  
    SELECT   
        p.name AS jogador,  
        COALESCE(p.position, 'Não Definida') AS posicao,  
        COALESCE(t.league\_name, 'Liga Não Especificada') AS liga,  
        t.name AS clube,  
        COALESCE(p.rating\_global, 0.0) AS rating\_global,  
        DENSE\_RANK() OVER (  
            PARTITION BY COALESCE(t.league\_name, 'Liga Não Especificada'), p.position   
            ORDER BY COALESCE(p.rating\_global, 0.0) DESC  
        ) AS ranking\_posicao  
    FROM players p  
    JOIN teams t ON p.team\_id \= t.id  
    WHERE p.rating\_global IS NOT NULL  
)  
SELECT   
    liga,  
    posicao,  
    ranking\_posicao,  
    jogador,  
    clube,  
    rating\_global  
FROM RankedPlayers  
WHERE ranking\_posicao \<= 5  
ORDER BY liga, posicao, ranking\_posicao;

### **2\. Comparativo do Elenco vs. Média da Liga (CTE Multi-Nível)**

* **Conceitos:** CTEs encadeadas, agregações AVG(), tratamento de divisão por zero e diferencial ROUND(a \- b, 2).  
* **Objetivo de Negócio:** Calcular a força relativa de cada clube contra seus concorrentes diretos na liga.

WITH LigaStats AS (  
    SELECT   
        COALESCE(t.league\_name, 'Liga Geral') AS liga,  
        ROUND(AVG(p.rating\_global), 2\) AS media\_liga  
    FROM players p  
    JOIN teams t ON p.team\_id \= t.id  
    WHERE p.rating\_global IS NOT NULL  
    GROUP BY COALESCE(t.league\_name, 'Liga Geral')  
),  
TeamStats AS (  
    SELECT   
        COALESCE(t.league\_name, 'Liga Geral') AS liga,  
        t.name AS clube,  
        COUNT(p.id) AS total\_jogadores,  
        ROUND(AVG(p.rating\_global), 2\) AS media\_clube  
    FROM players p  
    JOIN teams t ON p.team\_id \= t.id  
    WHERE p.rating\_global IS NOT NULL  
    GROUP BY COALESCE(t.league\_name, 'Liga Geral'), t.name  
)  
SELECT   
    ts.liga,  
    ts.clube,  
    ts.total\_jogadores,  
    ts.media\_clube,  
    ls.media\_liga,  
    ROUND(ts.media\_clube \- ls.media\_liga, 2\) AS diferencial\_forca  
FROM TeamStats ts  
JOIN LigaStats ls ON ts.liga \= ls.liga  
ORDER BY diferencial\_forca DESC  
LIMIT 10;

### **3\. Matriz de Maturidade Física e Faixa Etária (CASE WHEN & Funções Temporais)**

* **Conceitos:** CASE WHEN, cálculo de idade via strftime('%Y', 'now'), agrupamento por faixas etárias personalizadas.  
* **Objetivo de Negócio:** Analisar a distribuição do elenco entre promessas, pico performático e veteranos.

WITH PlayerAges AS (  
    SELECT   
        p.id,  
        p.name,  
        COALESCE(p.rating\_global, 0.0) AS rating\_global,  
        (CAST(strftime('%Y', 'now') AS INT) \- CAST(strftime('%Y', p.date\_of\_birth) AS INT)) AS idade  
    FROM players p  
    WHERE p.date\_of\_birth IS NOT NULL   
      AND p.date\_of\_birth \!= ''   
      AND length(p.date\_of\_birth) \>= 4  
)  
SELECT   
    CASE   
        WHEN idade \< 21 THEN '1. Promessa (\< 21 anos)'  
        WHEN idade BETWEEN 21 AND 23 THEN '2. Em Desenvolvimento (21-23)'  
        WHEN idade BETWEEN 24 AND 29 THEN '3. Pico Performático (24-29)'  
        WHEN idade BETWEEN 30 AND 34 THEN '4. Veterano Consolidado (30-34)'  
        ELSE '5. Final de Carreira (35+)'  
    END AS faixa\_etaria,  
    COUNT(id) AS quantidade\_atletas,  
    ROUND(AVG(idade), 1\) AS idade\_media,  
    ROUND(AVG(rating\_global), 2\) AS rating\_medio,  
    ROUND(MAX(rating\_global), 1\) AS rating\_maximo  
FROM PlayerAges  
GROUP BY faixa\_etaria  
ORDER BY faixa\_etaria;

### **4\. Variância e Equilíbrio de Plantel (Análise de Dispersão Estatística)**

* **Conceitos:** Cálculo manual da variância amostral ![][image1] em SQL, JOIN com subquery de agregações.  
* **Objetivo de Negócio:** Identificar elencos homogêneos vs. elencos altamente dependentes de poucas estrelas.

SELECT   
    COALESCE(t.league\_name, 'Liga Geral') AS liga,  
    t.name AS clube,  
    COUNT(p.id) AS num\_jogadores,  
    ROUND(AVG(p.rating\_global), 2\) AS rating\_medio,  
    ROUND(  
        AVG((p.rating\_global \- sub.media\_time) \* (p.rating\_global \- sub.media\_time)), 2  
    ) AS variancia\_elenco  
FROM players p  
JOIN teams t ON p.team\_id \= t.id  
JOIN (  
    SELECT team\_id, AVG(rating\_global) AS media\_time  
    FROM players  
    WHERE rating\_global IS NOT NULL  
    GROUP BY team\_id  
) sub ON p.team\_id \= sub.team\_id  
WHERE p.rating\_global IS NOT NULL  
GROUP BY COALESCE(t.league\_name, 'Liga Geral'), t.name  
HAVING num\_jogadores \>= 2  
ORDER BY variancia\_elenco DESC  
LIMIT 10;

### **5\. Principais Polos Exportadores de Talento (GROUP\_CONCAT & Top 5\)**

* **Conceitos:** GROUP\_CONCAT(), ROW\_NUMBER(), CTEs de classificação por partição e agregação condicional.  
* **Objetivo de Negócio:** Mapear a concentração e relevância de atletas de alta performance (rating\_global \>= 75\) por nacionalidade.

WITH RankedTopPlayers AS (  
    SELECT   
        p.nationality AS pais,  
        p.name AS jogador,  
        p.rating\_global,  
        ROW\_NUMBER() OVER (  
            PARTITION BY p.nationality   
            ORDER BY p.rating\_global DESC, p.name ASC  
        ) AS rk  
    FROM players p  
    WHERE p.rating\_global \>= 75 AND p.nationality IS NOT NULL  
),  
CountryTotals AS (  
    SELECT   
        p.nationality AS pais,  
        COUNT(p.id) AS total\_atletas\_top,  
        ROUND(AVG(p.rating\_global), 2\) AS rating\_medio\_top  
    FROM players p  
    WHERE p.rating\_global \>= 75 AND p.nationality IS NOT NULL  
    GROUP BY p.nationality  
)  
SELECT   
    ct.pais,  
    ct.total\_atletas\_top,  
    ct.rating\_medio\_top,  
    GROUP\_CONCAT(rtp.jogador, ', ') AS top\_5\_destaques  
FROM CountryTotals ct  
JOIN RankedTopPlayers rtp ON ct.pais \= rtp.pais  
WHERE rtp.rk \<= 5  
GROUP BY ct.pais, ct.total\_atletas\_top, ct.rating\_medio\_top  
HAVING ct.total\_atletas\_top \>= 2  
ORDER BY ct.total\_atletas\_top DESC, ct.rating\_medio\_top DESC;

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHQAAAAaCAYAAABmZHgNAAAFoElEQVR4Xu2aXWhcRRTHd2mEil/1I0bzNbtJNEYFlWil4oOUFlrwA1rRIqI+WR+ioBAL8aUQhEr1QVu1hGrpkxoCodQvbMFiAw1axIKiCHlQSkuVUihUhGL09987N0xO9mZzbzbpruwfDvfec+bjzDkzZ87Mbi5XAYVCYVVPT8/Vlt9AfaGps7NzHbTHOXeSZ78t0MDSg8W0Evv38brCytIi39bWdj2NFaEfGg5dfnR0dNyL3ffh1E/wwYlisehsmdSgoZuzOJQ6h6jze1bq6uq61bYZgsnW3tvbe5Xl1xtw1lYeecsHTdjwQ2gIe1zL8zvoHVsoNbI6FIdcQ73D0L/QSH9//2W2TALylF8LTaoNK2xvb78cIxyAXrCyekR3d/eNchb2XW9lMWKHMubtVpYaWR0qUO8e6JycmtYB1DkOrbF89HhaztZ2YGW1BCbedYz5MfR93BKytrBspTF5+dckps1WlhqLcajAoJ6k/rQcyx6w2sqTQPlN0Jshz6/6SWgg5NciChHeRtcRS/DvDsvKwfCn4G8J+THgj0I3WX4mLNahCrV+IFql35QLowlYoVCTC/YXvh+knTNZdalh5BnTPsY2xntTKIDX19LScgW2WwltsPIFQw3Q2CD0qYtW2FF4O6BVtmwlKIGh/s9yKoq/n8uoFPVfd9F+I0eXwwrtSSK9Nzc3X6kJqbHYgssB74TYXqVTQ6xbWE6g3FZ0PSlbxTxltWCneIz5Cd5fC+tcUqDw/Sh0AfoH2mzlleAn2GeuzCwW4PdBE5Tbz/MY9AU0iSE+5nk8NNQyQCvuGfUvJ0FD0LvodoDnkXKT2kefc3rq24933EVJZUyvhHUuNTTIV71ip6ywErQqXZS677UynymOxec09qRb+P7DR4aDvs+Ntt5SAV3X098ubTc45jnf/zDnyjt5/glNoWuLqdPvogm/KeTXNHTkiA2cYi8twUV7+W8MfJuV+XA1kyj52X7Rh9zPoQnVD+ssFXyY3S/n6dtF28RffN+HE+/i/bR4ubl7ZeL4MoMGP0hLto1K0CpC6V+hl6xsPsw3YCUN4TnXO3g6LJMEH9qUK8zJRhNoUHVsOwHy/sKjlMy5aJv4qbW19QZTbhbcPOOraWhlYpBRy6+EeMDQkJWFkOFkQBnSs2YZeLmBHtOaYPG3Jp4mYFhGcFEOcDYsW/PwR5hdLkNS5MPnEYUzI9LN0lvQRWQPxeE2drxCn+pUWFVVg9/Pv4dO+LvwUriN5XwPlHOa30PPu6XY6/1seQ8aoaPnc352S0GUeUN86AFTrRJkeIW2Qb1b4UJA3b3Q4XCGy4AK4S7KEGWUYRcdj7b5PVtjSLxWqzawzwb1z/Mrf+y4IL0k88nauD+6zAJlHkF21kW/rFQfKHQbjf/iorS7GPAL/uI8lVNoY7PzmZ+VJWDOxYJmtvQxRxBdYu920ZFFx4KdLjomSG8dER4O21hqSDf0+Ja+x6CjLjo+HVOU4HlQ9rN1BBclT2Xvr6sCGl+LMV70hpnJIF2GGUQ76xjHaBpl/UyfdfWnvqFTkoV8UDq0F4JLD4XoFJOnqlC/OpYUojBf0s3f05adWMF2st3KqgZloYSIHhfN/pmZ41LGeAa2mjoTCj9WNh+o86MmgmFrNSrsfqR3I6tbMJ410BTjvcPKqgLNLO1B2qt8Z+fjVSFH2/JJ8HuInLngS3mBPm53Cam+Bt0ZHXv+L/e58SQdziWs4EUDY3XFjlNiwfuXWhXa01yFY0MM/8uIzmDzZrRxeFLCwKR5lvKHXHSzkvhjLrKnoHHLr0eQAT8qO6XZjlLDRT8wz4RWF/2UdQaDb3ELvE90/heWrFQm3IbIo8vLelpBvYGxjqfdjlIDY+2wf++g4wHotFZvyG+gxoHTNkJ/Q7vDv27yXcSZe3zm1kADDTTQQCb8B2ivtvLRgBWxAAAAAElFTkSuQmCC>