# 🤝 Guia de Contribuição

Obrigado por querer contribuir com o Sales Agent! Este guia explica como fazer isso.

---

## 📋 Código de Conduta

Nós nos comprometemos a proporcionar um ambiente acolhedor e inclusivo.

**Esperamos que você:**
- Seja respeitoso com outros contribuidores
- Considere perspectivas diferentes
- Foque na questão, não na pessoa
- Reporte comportamento inaceitável

---

## 🐛 Reportando Bugs

### Antes de Reportar

- [ ] Procure em issues já abertas
- [ ] Verifique `TROUBLESHOOTING.md`
- [ ] Leia `FAQ.md`
- [ ] Tente a solução sugerida

### Ao Reportar

**Template:**

```markdown
## Descrição do Bug
[Descrição clara do problema]

## Como Reproduzir
1. Faça isso
2. Depois isso
3. Resultado inesperado

## Comportamento Esperado
[O que deveria acontecer]

## Logs
[Cole os logs relevantes]

## Ambiente
- Docker: [versão]
- Python: [versão]
- Sistema: [Windows/Mac/Linux]
```

---

## 💡 Sugerindo Melhorias

### Antes de Sugerir

- [ ] Verifique se já não existe
- [ ] Considere se é realmente necessário
- [ ] Pense nos impactos

### Ao Sugerir

**Template:**

```markdown
## Resumo
[Uma linha descrevendo a melhoria]

## Motivação
Por que isso seria útil?

## Solução Proposta
Como você implementaria?

## Alternativas Consideradas
Outras abordagens?

## Contexto Adicional
Mais detalhes se necessário
```

---

## 🛠️ Contribuindo com Código

### Setup Local

```bash
# 1. Fork o repositório
# 2. Clone seu fork
git clone https://github.com/seu-usuario/sales-agent.git
cd sales-agent

# 3. Crie uma branch
git checkout -b feature/sua-feature

# 4. Setup development
docker-compose up -d
python -m pytest tests/
```

### Workflow

1. **Crie uma branch descritiva**
   ```bash
   git checkout -b feature/adiciona-suporte-a-groq
   # ou
   git checkout -b fix/webhook-timeout
   ```

2. **Faça suas mudanças**
   - Mantenha commits pequenos e descritivos
   - Um commit = uma mudança lógica
   - Use mensagens em inglês: `"Add support for Groq API"`

3. **Escreva/atualize testes**
   ```bash
   pytest tests/ -v
   ```

4. **Atualize documentação**
   - Se adicionar feature, atualize README.md
   - Se mudar arquivo, atualize STRUCTURE.md
   - Se corrigir bug, mencione em CHANGELOG.md

5. **Commit e Push**
   ```bash
   git commit -m "Add Groq API support"
   git push origin feature/adiciona-groq
   ```

6. **Abra Pull Request**
   - Descrição clara do que foi feito
   - Reference issue relacionada: "Closes #123"
   - Mencione breaking changes se houver

---

## 📝 Padrões de Código

### Python

```python
# ✅ Bom
async def send_message(phone: str, text: str) -> None:
    """Envia mensagem via WhatsApp."""
    logger.info("Enviando mensagem.", phone=phone)
    await whatsapp_api.send(phone, text)


# ❌ Ruim
async def send_message(phone, text):
    print(f"Enviando para {phone}")
    await whatsapp_api.send(phone, text)
```

**Diretrizes:**
- Type hints obrigatório
- Docstrings para funções públicas
- Logging com structlog
- PEP 8 style
- Max 120 caracteres por linha

### Commits

```bash
# ✅ Bom
git commit -m "Add audio upload to Meta API

- Implement upload_audio() function
- Add retry logic with exponential backoff
- Update scripts with new media IDs
- Add tests for upload_audio()"

# ❌ Ruim
git commit -m "fix bugs and add stuff"
```

**Formato:**
```
[Tipo] Breve descrição (max 50 chars)

Explicação detalhada do que foi mudado
e por quê (max 72 chars por linha)

- Bullet points de mudanças específicas
- Outra mudança importante
```

**Tipos:**
- `feat:` — Nova feature
- `fix:` — Bug fix
- `docs:` — Documentação
- `style:` — Formatting (sem mudança de lógica)
- `refactor:` — Refatoração
- `perf:` — Performance
- `test:` — Testes

---

## ✅ Checklist antes de PR

- [ ] Código segue padrões do projeto
- [ ] Testes passam: `pytest`
- [ ] Documentação atualizada
- [ ] Sem breaking changes (ou bem documentado)
- [ ] Commit messages descritivas
- [ ] Sem `console.log()` ou `print()` (use logger)
- [ ] Nenhuma credencial em commits
- [ ] Compatível com versão anterior

---

## 🧪 Testes

### Rodando Testes

```bash
# Todos os testes
pytest tests/ -v

# Um arquivo específico
pytest tests/test_agents.py -v

# Com coverage
pytest tests/ --cov=app
```

### Escrevendo Testes

```python
import pytest
from app.models.lead import Lead, LeadStage

@pytest.mark.asyncio
async def test_create_lead():
    """Testa criação de novo lead."""
    lead = Lead(
        phone_number="5511999999999",
        name="João"
    )
    
    assert lead.phone_number == "5511999999999"
    assert lead.stage == LeadStage.NEW
```

---

## 📚 Documentação

### Adicionando Documentação

1. **README.md** — Para features principais
2. **FAQ.md** — Para perguntas esperadas
3. **Docstrings** — Para código Python
4. **Comentários** — Para lógica complexa

### Exemplo de Docstring

```python
async def identify_course(lead: Lead, user_message: str) -> CourseSlug:
    """
    Identifica qual curso o lead está interessado.
    
    Usa Claude para analisar a mensagem e o histórico da conversa,
    retornando o slug do curso identificado ou UNKNOWN.
    
    Args:
        lead: Lead cujo curso deve ser identificado
        user_message: Mensagem do lead
    
    Returns:
        CourseSlug do curso identificado ou CourseSlug.UNKNOWN
    
    Raises:
        ValueError: Se lead é None
    """
```

---

## 🔍 Code Review

Quando você recebe feedback:

- ✅ Agradeça o feedback
- ✅ Explique sua perspectiva se discordar
- ✅ Faça as mudanças sugeridas
- ✅ Considere feedback construtivamente
- ✅ Não leve para o lado pessoal

Quando você revisa código:

- ✅ Seja respeitoso e construtivo
- ✅ Sugira melhorias, não ordene
- ✅ Explique o porquê
- ✅ Aprenda com o outro também

---

## 🚀 Suas Contribuições Importam

**Tipos de contribuição que ajudam:**

- 🐛 Reportar e corrigir bugs
- ✨ Adicionar novas features
- 📖 Melhorar documentação
- 🧪 Escrever testes
- 💬 Responder perguntas em issues
- 📝 Melhorar exemplos
- 🌐 Traduzir para outros idiomas
- 🎨 Design e UX

---

## 💬 Comunicação

- **Issues:** Para bugs, features, perguntas
- **Discussions:** Para ideias e debates
- **Pull Requests:** Para enviar código
- **Email:** Para assuntos privados

---

## 🏆 Reconhecimento

Contribuidores são reconhecidos em:

- [CONTRIBUTORS.md](CONTRIBUTORS.md)
- Commits e PRs no GitHub
- Release notes quando aplicável

---

## ❓ Dúvidas?

Não tenha medo de perguntar!

- Abra uma issue
- Participe das discussions
- Procure em FAQ.md

**Toda contribuição, por menor que seja, é apreciada! 🙏**

---

**Obrigado por contribuir com Sales Agent! 🚀**
