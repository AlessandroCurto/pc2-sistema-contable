/* Chatbot flotante — Sistema y Gestión Financiera */
(function () {
  'use strict';

  const ENDPOINT = '/chatbot/';
  const SUGERENCIAS = [
    '¿Cómo registro un asiento?',
    '¿Cómo resolver un caso con IGV?',
    '¿Qué es el Balance de Comprobación?',
    '¿Cómo importar asientos desde Excel?',
    '¿Cómo calcular el costo de ventas?',
  ];

  let historial = [];    // [{role, content}]
  let enviando = false;
  let panelAbierto = false;

  /* ---- Construir el HTML ---- */
  function crear() {
    // Botón flotante
    const boton = document.createElement('button');
    boton.className = 'chat-boton';
    boton.setAttribute('aria-label', 'Abrir asistente virtual');
    boton.setAttribute('aria-expanded', 'false');
    boton.setAttribute('aria-controls', 'chat-panel');
    boton.innerHTML = `
      <svg class="chat-boton-icono" width="28" height="28" viewBox="0 0 32 32" fill="none"
           aria-hidden="true" focusable="false">
        <!-- robot cabeza -->
        <rect x="6" y="8" width="20" height="14" rx="4" fill="#f2c200"/>
        <!-- ojos -->
        <circle cx="12" cy="13" r="2.5" fill="#0a0a0a"/>
        <circle cx="20" cy="13" r="2.5" fill="#0a0a0a"/>
        <!-- boca -->
        <rect x="11" y="18" width="10" height="2" rx="1" fill="#0a0a0a"/>
        <!-- antena -->
        <line x1="16" y1="8" x2="16" y2="4" stroke="#f2c200" stroke-width="2" stroke-linecap="round"/>
        <circle cx="16" cy="3" r="1.5" fill="#f2c200"/>
        <!-- cuerpo -->
        <rect x="10" y="22" width="12" height="6" rx="2" fill="#f2c200" opacity=".7"/>
      </svg>
      <span class="chat-boton-cerrar" aria-hidden="true">✕</span>`;

    // Panel
    const panel = document.createElement('div');
    panel.id = 'chat-panel';
    panel.className = 'chat-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Asistente virtual');
    panel.setAttribute('aria-modal', 'false');

    panel.innerHTML = `
      <div class="chat-cabecera">
        <div class="chat-cabecera-robot" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 32 32" fill="none">
            <rect x="6" y="8" width="20" height="14" rx="4" fill="#0a0a0a"/>
            <circle cx="12" cy="13" r="2.5" fill="#f2c200"/>
            <circle cx="20" cy="13" r="2.5" fill="#f2c200"/>
            <rect x="11" y="18" width="10" height="2" rx="1" fill="#f2c200"/>
            <line x1="16" y1="8" x2="16" y2="4" stroke="#0a0a0a" stroke-width="2" stroke-linecap="round"/>
            <circle cx="16" cy="3" r="1.5" fill="#0a0a0a"/>
          </svg>
        </div>
        <div class="chat-cabecera-info">
          <div class="chat-cabecera-nombre">Asistente Contable</div>
          <div class="chat-cabecera-estado">
            <span class="chat-punto-verde"></span>
            En línea · siempre disponible
          </div>
        </div>
      </div>

      <div class="chat-mensajes" id="chat-mensajes" role="log" aria-live="polite" aria-label="Conversación"></div>

      <div class="chat-sugerencias" id="chat-sugerencias" aria-label="Preguntas sugeridas"></div>

      <div class="chat-entrada">
        <textarea
          class="chat-textarea"
          id="chat-textarea"
          placeholder="Escribe tu pregunta..."
          rows="1"
          aria-label="Mensaje para el asistente"
          maxlength="2000"
        ></textarea>
        <button class="chat-enviar" id="chat-enviar" aria-label="Enviar mensaje" disabled>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>`;

    document.body.appendChild(boton);
    document.body.appendChild(panel);
    return { boton, panel };
  }

  /* ---- Formatear markdown básico ---- */
  function formatearMd(texto) {
    return texto
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/^- (.+)/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
      .replace(/\n{2,}/g, '</p><p>')
      .replace(/\n/g, '<br>')
      .replace(/^(.+)$/, '<p>$1</p>');
  }

  /* ---- Agregar mensaje a la UI ---- */
  function agregarMensaje(texto, rol, contenedor) {
    const div = document.createElement('div');
    div.className = `chat-burbuja chat-burbuja-${rol === 'assistant' ? 'bot' : 'usuario'}`;
    div.innerHTML = rol === 'assistant' ? formatearMd(texto) : escHtml(texto);
    contenedor.appendChild(div);
    contenedor.scrollTop = contenedor.scrollHeight;
    return div;
  }

  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  /* ---- Mostrar dots de "escribiendo..." ---- */
  function mostrarEscribiendo(contenedor) {
    const div = document.createElement('div');
    div.className = 'chat-escribiendo';
    div.setAttribute('aria-label', 'El asistente está escribiendo');
    div.innerHTML = '<span></span><span></span><span></span>';
    contenedor.appendChild(div);
    contenedor.scrollTop = contenedor.scrollHeight;
    return div;
  }

  /* ---- Chips de sugerencias ---- */
  function pintarSugerencias(contenedor, onClic) {
    contenedor.innerHTML = '';
    SUGERENCIAS.forEach(texto => {
      const chip = document.createElement('button');
      chip.className = 'chat-chip';
      chip.textContent = texto;
      chip.setAttribute('type', 'button');
      chip.addEventListener('click', () => onClic(texto));
      contenedor.appendChild(chip);
    });
  }

  /* ---- Llamada al backend ---- */
  async function preguntar(texto, mensajesContenedor, sugerenciasContenedor) {
    if (enviando || !texto.trim()) return;
    enviando = true;

    const btnEnviar = document.getElementById('chat-enviar');
    const textarea = document.getElementById('chat-textarea');
    btnEnviar.disabled = true;
    sugerenciasContenedor.style.display = 'none';

    // Mensaje del usuario
    historial.push({ role: 'user', content: texto });
    agregarMensaje(texto, 'user', mensajesContenedor);
    textarea.value = '';
    textarea.style.height = 'auto';

    // Indicador de escritura
    const dots = mostrarEscribiendo(mensajesContenedor);

    try {
      const resp = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mensajes: historial }),
      });
      const datos = await resp.json();
      dots.remove();

      const respTexto = datos.respuesta || 'Lo siento, ocurrió un error.';
      historial.push({ role: 'assistant', content: respTexto });
      agregarMensaje(respTexto, 'assistant', mensajesContenedor);
    } catch (_) {
      dots.remove();
      agregarMensaje('Error de red. Verifica tu conexión.', 'assistant', mensajesContenedor);
    }

    enviando = false;
    btnEnviar.disabled = !textarea.value.trim();
    textarea.focus();
  }

  /* ---- Abrir / cerrar ---- */
  function togglePanel(boton, panel) {
    panelAbierto = !panelAbierto;
    document.body.classList.toggle('chat-abierto', panelAbierto);
    boton.setAttribute('aria-expanded', panelAbierto ? 'true' : 'false');
    boton.classList.remove('chat-pulsando');

    if (panelAbierto) {
      panel.removeAttribute('inert');
      // Foco al textarea después de la transición
      setTimeout(() => {
        const ta = document.getElementById('chat-textarea');
        if (ta) ta.focus();
      }, 380);
    } else {
      panel.setAttribute('inert', '');
      boton.focus();
    }
  }

  /* ---- Bienvenida inicial ---- */
  function bienvenida(contenedor) {
    const msgs = [
      '¡Hola! 👋 Soy tu asistente contable. Puedo ayudarte a resolver casos, explicarte la teoría y guiarte con el sistema.',
      '¿En qué te puedo ayudar hoy?',
    ];
    msgs.forEach((m, i) => {
      setTimeout(() => {
        const burbuja = agregarMensaje(m, 'assistant', contenedor);
        void burbuja; // evitar warning
      }, i * 600);
    });
  }

  /* ---- Init ---- */
  function init() {
    const { boton, panel } = crear();
    const mensajesContenedor = panel.querySelector('#chat-mensajes');
    const sugerenciasContenedor = panel.querySelector('#chat-sugerencias');
    const textarea = panel.querySelector('#chat-textarea');
    const btnEnviar = panel.querySelector('#chat-enviar');

    panel.setAttribute('inert', '');

    // Bienvenida
    bienvenida(mensajesContenedor);
    // Sugerencias iniciales (aparecen luego)
    setTimeout(() => {
      pintarSugerencias(sugerenciasContenedor, (txt) => {
        togglePanel(boton, panel);
        preguntar(txt, mensajesContenedor, sugerenciasContenedor);
      });
    }, 1400);

    // Toggle panel
    boton.addEventListener('click', () => togglePanel(boton, panel));

    // Cerrar con Esc
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && panelAbierto) togglePanel(boton, panel);
    });

    // Auto-resize textarea
    textarea.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 96) + 'px';
      btnEnviar.disabled = !textarea.value.trim();
    });

    // Enviar con Enter (Shift+Enter = nueva línea)
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!enviando && textarea.value.trim()) {
          preguntar(textarea.value.trim(), mensajesContenedor, sugerenciasContenedor);
        }
      }
    });

    // Botón enviar
    btnEnviar.addEventListener('click', () => {
      if (!enviando && textarea.value.trim()) {
        preguntar(textarea.value.trim(), mensajesContenedor, sugerenciasContenedor);
      }
    });

    // Pulso en el botón cuando el chat está cerrado y hay respuesta
    setInterval(() => {
      if (!panelAbierto && historial.length > 0) {
        boton.classList.add('chat-pulsando');
        setTimeout(() => boton.classList.remove('chat-pulsando'), 1700);
      }
    }, 8000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
