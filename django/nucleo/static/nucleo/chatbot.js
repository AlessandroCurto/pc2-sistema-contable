/* Asistente del Sistema y Gestión Financiera.
   La respuesta se escribe mientras el modelo la produce (SSE), la conversación
   sobrevive al cambio de pantalla (sessionStorage) y el texto se arma con un
   lector de markdown por líneas, no con una cadena de reemplazos. */
(function () {
  'use strict';

  var RUTA = '/chatbot/';
  var RUTA_REGISTRAR = '/asistente/registrar/';
  var MEMORIA = 'sgf:conversacion';
  var ABIERTO = 'sgf:asistente-abierto';
  var TOPE_GUARDADO = 40;

  var SUGERENCIAS = [
    'Resolver un enunciado',
    'Abre el caso...',
    '¿Cómo está mi caso?',
    '¿Por qué no cuadra?',
    '¿Cómo registro un asiento?',
    '¿Cómo se calcula el IGV?',
    'Importar desde Excel',
    '¿Qué va al Debe y qué al Haber?',
  ];

  var historial = [];
  var ocupado = false;
  var abierto = false;
  var cancelar = null;
  var nodos = {};

  /* ---------------------------------------------------------- utilidades */

  function escapar(texto) {
    return texto
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  /** Negritas, cursivas y `código` dentro de una línea ya escapada. */
  function enLinea(texto) {
    return escapar(texto)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\[([^\]]+)\]\((\/[^)\s]*)\)/g, '<a href="$2">$1</a>')
      .replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  }

  /** Markdown por bloques: párrafos, listas, tablas, títulos y código. */
  function marcar(texto) {
    var lineas = texto.replace(/\r/g, '').split('\n');
    var salida = [];
    var parrafo = [];
    var lista = null;      // 'ul' | 'ol'
    var enCodigo = false;
    var codigo = [];

    function cerrarParrafo() {
      if (parrafo.length) {
        salida.push('<p>' + parrafo.map(enLinea).join('<br>') + '</p>');
        parrafo = [];
      }
    }
    function cerrarLista() {
      if (lista) {
        salida.push('</' + lista + '>');
        lista = null;
      }
    }
    function cerrarTodo() {
      cerrarParrafo();
      cerrarLista();
    }

    for (var i = 0; i < lineas.length; i++) {
      var linea = lineas[i];

      if (/^\s*```/.test(linea)) {
        if (enCodigo) {
          salida.push('<pre><code>' + escapar(codigo.join('\n')) + '</code></pre>');
          codigo = [];
          enCodigo = false;
        } else {
          cerrarTodo();
          enCodigo = true;
        }
        continue;
      }
      if (enCodigo) { codigo.push(linea); continue; }

      // Tabla: | a | b |  seguida de | --- | --- |
      if (/^\s*\|.*\|\s*$/.test(linea) && /^\s*\|[\s:|-]+\|\s*$/.test(lineas[i + 1] || '')) {
        cerrarTodo();
        var celdas = function (fila) {
          return fila.trim().replace(/^\||\|$/g, '').split('|').map(function (c) {
            return c.trim();
          });
        };
        var cabecera = celdas(linea);
        var html = '<table><thead><tr>';
        cabecera.forEach(function (c) { html += '<th>' + enLinea(c) + '</th>'; });
        html += '</tr></thead><tbody>';
        i += 2;
        while (i < lineas.length && /^\s*\|.*\|\s*$/.test(lineas[i])) {
          html += '<tr>';
          celdas(lineas[i]).forEach(function (c) {
            var numero = /^[-(]?[\d.,]+\)?$/.test(c);
            html += '<td' + (numero ? ' class="num"' : '') + '>' + enLinea(c) + '</td>';
          });
          html += '</tr>';
          i++;
        }
        i--;
        salida.push(html + '</tbody></table>');
        continue;
      }

      var titulo = linea.match(/^\s{0,3}(#{2,6})\s+(.+)$/);
      if (titulo) {
        cerrarTodo();
        salida.push('<h4>' + enLinea(titulo[2]) + '</h4>');
        continue;
      }

      var vinheta = linea.match(/^\s*[-*+]\s+(.+)$/);
      var numerada = linea.match(/^\s*\d+[.)]\s+(.+)$/);
      if (vinheta || numerada) {
        cerrarParrafo();
        var quiere = vinheta ? 'ul' : 'ol';
        if (lista !== quiere) { cerrarLista(); salida.push('<' + quiere + '>'); lista = quiere; }
        salida.push('<li>' + enLinea((vinheta || numerada)[1]) + '</li>');
        continue;
      }

      if (!linea.trim()) { cerrarTodo(); continue; }

      cerrarLista();
      parrafo.push(linea.trim());
    }

    if (enCodigo && codigo.length) {
      salida.push('<pre><code>' + escapar(codigo.join('\n')) + '</code></pre>');
    }
    cerrarTodo();
    return salida.join('');
  }

  function pegadoAbajo() {
    var c = nodos.mensajes;
    return c.scrollHeight - c.scrollTop - c.clientHeight < 60;
  }
  function alFinal(forzar) {
    if (forzar) nodos.mensajes.scrollTop = nodos.mensajes.scrollHeight;
  }

  /* ------------------------------------------------------------- memoria */

  function guardar() {
    try {
      sessionStorage.setItem(MEMORIA, JSON.stringify(historial.slice(-TOPE_GUARDADO)));
    } catch (_) { /* modo privado: la conversación vive solo en la pantalla */ }
  }
  function recuperar() {
    try {
      var crudo = sessionStorage.getItem(MEMORIA);
      if (!crudo) return [];
      var datos = JSON.parse(crudo);
      return Array.isArray(datos) ? datos : [];
    } catch (_) { return []; }
  }

  /* -------------------------------------------------------------- burbujas */

  function burbuja(rol) {
    var div = document.createElement('div');
    div.className = 'chat-burbuja chat-burbuja-' + (rol === 'assistant' ? 'bot' : 'usuario');
    nodos.mensajes.appendChild(div);
    return div;
  }

  function pintar(texto, rol, animar) {
    var div = burbuja(rol);
    if (!animar) div.style.animation = 'none';
    div.innerHTML = rol === 'assistant' ? marcar(texto) : enLinea(texto);
    return div;
  }

  function puntos() {
    var div = document.createElement('div');
    div.className = 'chat-escribiendo';
    div.innerHTML = '<span></span><span></span><span></span>';
    nodos.mensajes.appendChild(div);
    alFinal(true);
    return div;
  }

  function botonRegistrar(texto) {
    var caja = document.createElement('div');
    caja.className = 'chat-accion';
    var boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'chat-boton-accion';
    boton.textContent = 'Registrar estos asientos en el caso';
    var pie = document.createElement('p');
    pie.className = 'chat-accion-pie';
    pie.textContent = 'Revísalos antes. Se guardan en el Libro Diario.';
    if (/Creé |preparé un|A tu plan/.test(nodos.mensajes.textContent || '')) {
      pie.textContent = 'Revísalos antes. Creo lo que falte y los guardo.';
    }
    caja.appendChild(boton);
    caja.appendChild(pie);
    nodos.mensajes.appendChild(caja);
    alFinal(true);

    boton.addEventListener('click', function () {
      boton.disabled = true;
      boton.textContent = 'Registrando…';
      fetch(RUTA_REGISTRAR, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': nodos.raiz.dataset.csrf || '',
        },
        body: JSON.stringify({ texto: texto }),
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          caja.remove();
          if (d.error) { aviso(d.error); return; }
          var partes = [];
          if (d.caso) partes.push('Creé el caso **' + d.caso + '**.');
          if (d.cuentas) partes.push('Agregué ' + d.cuentas + ' cuenta(s) al plan.');
          partes.push(
            'Guardé **' + d.guardados + ' asiento(s)**. ' +
            'Los ves en el [Libro Diario](' + d.url + ').'
          );
          pintar(partes.join(' '), 'assistant', true);
          (d.errores || []).forEach(function (e) { aviso(e); });
        })
        .catch(function () {
          caja.remove();
          aviso('No se pudieron registrar. Inténtalo de nuevo.');
        });
    });
  }

  function aviso(texto) {
    var div = document.createElement('div');
    div.className = 'chat-aviso';
    div.setAttribute('role', 'alert');
    div.textContent = texto;
    nodos.mensajes.appendChild(div);
    alFinal(true);
  }

  /* ------------------------------------------------------------ preguntar */

  function preguntar(texto) {
    texto = (texto || '').trim();
    if (ocupado || !texto) return;
    ocupado = true;
    nodos.sugerencias.hidden = true;
    nodos.caja.value = '';
    nodos.caja.style.height = 'auto';
    refrescarBoton();

    historial.push({ role: 'user', content: texto });
    pintar(texto, 'user', true);
    guardar();
    alFinal(true);

    var esperando = puntos();
    var destino = null;
    var acumulado = '';
    var accionPendiente = null;
    var recargar = false;
    var control = new AbortController();
    cancelar = function () { control.abort(); };

    fetch(RUTA, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': nodos.raiz.dataset.csrf || '',
      },
      body: JSON.stringify({ mensajes: historial }),
      signal: control.signal,
    })
      .then(function (respuesta) {
        if (!respuesta.ok && respuesta.headers.get('content-type') === 'application/json') {
          return respuesta.json().then(function (d) { throw new Error(d.error || ''); });
        }
        if (!respuesta.body) throw new Error('');
        var lector = respuesta.body.getReader();
        var decodificador = new TextDecoder();
        var resto = '';

        function recibir(trozo) {
          if (!destino) {
            esperando.remove();
            destino = burbuja('assistant');
            destino.setAttribute('aria-busy', 'true');
          }
          var abajo = pegadoAbajo();
          acumulado += trozo;
          destino.innerHTML = marcar(acumulado);
          alFinal(abajo);
        }

        function leer() {
          return lector.read().then(function (r) {
            if (r.done) return;
            resto += decodificador.decode(r.value, { stream: true });
            var partes = resto.split('\n\n');
            resto = partes.pop();
            partes.forEach(function (bloque) {
              var linea = bloque.replace(/^data:\s?/, '');
              if (!linea) return;
              var dato;
              try { dato = JSON.parse(linea); } catch (_) { return; }
              if (dato.t) recibir(dato.t);
              else if (dato.accion === 'registrar') accionPendiente = dato.texto;
              else if (dato.accion === 'recargar') recargar = true;
              else if (dato.error) { esperando.remove(); aviso(dato.error); }
            });
            return leer();
          });
        }
        return leer();
      })
      .catch(function (error) {
        esperando.remove();
        if (error && error.name === 'AbortError') return;
        aviso((error && error.message) || 'No se pudo conectar con el asistente.');
      })
      .then(function () {
        esperando.remove();
        if (destino) {
          destino.removeAttribute('aria-busy');
          if (acumulado.trim()) {
            historial.push({ role: 'assistant', content: acumulado });
            guardar();
          } else {
            destino.remove();
          }
        }
        if (accionPendiente) botonRegistrar(accionPendiente);
        if (recargar) { guardar(); setTimeout(function () { location.reload(); }, 900); }
        ocupado = false;
        cancelar = null;
        refrescarBoton();
        if (abierto) nodos.caja.focus();
      });
  }

  /* ------------------------------------------------------------- pantalla */

  function refrescarBoton() {
    var hayTexto = !!nodos.caja.value.trim();
    nodos.enviar.disabled = !hayTexto && !ocupado;
    nodos.enviar.classList.toggle('chat-enviar-detener', ocupado);
    nodos.enviar.setAttribute('aria-label', ocupado ? 'Detener respuesta' : 'Enviar mensaje');
    nodos.limpiar.hidden = historial.length === 0;
  }

  function alternar(forzar) {
    abierto = typeof forzar === 'boolean' ? forzar : !abierto;
    document.body.classList.toggle('chat-abierto', abierto);
    nodos.boton.setAttribute('aria-expanded', abierto ? 'true' : 'false');
    if (abierto) {
      nodos.panel.removeAttribute('inert');
      alFinal(true);
      setTimeout(function () { nodos.caja.focus(); }, 320);
    } else {
      nodos.panel.setAttribute('inert', '');
    }
    try { sessionStorage.setItem(ABIERTO, abierto ? '1' : '0'); } catch (_) {}
  }

  function limpiar() {
    historial = [];
    guardar();
    nodos.mensajes.innerHTML = '';
    bienvenida(false);
    nodos.sugerencias.hidden = false;
    refrescarBoton();
  }

  function bienvenida(animar) {
    var div = pintar(
      'Hola, soy **MULUNI**. Puedo resolver un enunciado que me pegues, revisar el caso ' +
        'que tienes abierto con sus cifras reales, abrirte otro caso y explicarte la ' +
        'teoría. ¿Qué necesitas?',
      'assistant',
      animar
    );
    div.classList.add('chat-burbuja-saludo');
  }

  /* ----------------------------------------------------------------- init */

  function construir(avatar) {
    var raiz = document.createElement('div');
    raiz.className = 'chat-raiz';
    raiz.innerHTML =
      '<button class="chat-boton" type="button" aria-expanded="false" aria-controls="chat-panel"' +
      ' aria-label="Abrir a MULUNI, el asistente contable">' +
        '<img class="chat-boton-avatar" alt="" width="40" height="40" src="' + avatar + '">' +
        '<svg class="chat-boton-cerrar" width="22" height="22" viewBox="0 0 24 24" fill="none"' +
        ' stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">' +
          '<path d="M6 6l12 12M18 6L6 18"/>' +
        '</svg>' +
      '</button>' +

      '<section class="chat-panel" id="chat-panel" role="dialog" aria-label="MULUNI, asistente contable" inert>' +
        '<header class="chat-cabecera">' +
          '<span class="chat-insignia" aria-hidden="true">' +
            '<img alt="" width="26" height="26" src="' + avatar + '">' +
          '</span>' +
          '<span class="chat-cabecera-texto">' +
            '<strong>MULUNI</strong>' +
            '<span class="chat-cabecera-pie" data-caso></span>' +
          '</span>' +
          '<button class="chat-icono-boton" type="button" data-limpiar hidden' +
          ' aria-label="Empezar una conversación nueva" title="Empezar de nuevo">' +
            '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
            ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
              '<path d="M3 2v6h6"/><path d="M3.5 13a9 9 0 1 0 2.1-5.6L3 8"/>' +
            '</svg>' +
          '</button>' +
        '</header>' +

        '<div class="chat-mensajes" data-mensajes role="log" aria-live="polite" aria-atomic="false"></div>' +

        '<div class="chat-sugerencias" data-sugerencias></div>' +

        '<form class="chat-entrada" data-form>' +
          '<label class="chat-etiqueta" for="chat-caja">Tu pregunta</label>' +
          '<textarea id="chat-caja" class="chat-caja" rows="1" maxlength="4000"' +
          ' placeholder="Escribe o pega tu enunciado…"></textarea>' +
          '<button class="chat-enviar" type="submit" aria-label="Enviar mensaje" disabled>' +
            '<svg class="chat-icono-enviar" width="17" height="17" viewBox="0 0 24 24" fill="none"' +
            ' stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"' +
            ' aria-hidden="true"><path d="M4 12l16-8-6 16-2.5-6.5L4 12z"/></svg>' +
            '<svg class="chat-icono-detener" width="15" height="15" viewBox="0 0 24 24"' +
            ' aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2.5" fill="currentColor"/></svg>' +
          '</button>' +
        '</form>' +
      '</section>';

    document.body.appendChild(raiz);
    return raiz;
  }

  function init() {
    var meta = document.getElementById('chat-datos');
    var raiz = construir((meta && meta.dataset.avatar) || '');
    nodos = {
      raiz: raiz,
      boton: raiz.querySelector('.chat-boton'),
      panel: raiz.querySelector('.chat-panel'),
      mensajes: raiz.querySelector('[data-mensajes]'),
      sugerencias: raiz.querySelector('[data-sugerencias]'),
      caja: raiz.querySelector('.chat-caja'),
      enviar: raiz.querySelector('.chat-enviar'),
      limpiar: raiz.querySelector('[data-limpiar]'),
      pie: raiz.querySelector('[data-caso]'),
      form: raiz.querySelector('[data-form]'),
    };

    raiz.dataset.csrf = (meta && meta.dataset.csrf) || '';
    var caso = (meta && meta.dataset.caso) || '';
    nodos.pie.textContent = caso ? 'Viendo: ' + caso : 'Sin ningún caso abierto';

    // Conversación anterior, si la hay.
    historial = recuperar();
    if (historial.length) {
      historial.forEach(function (m) { pintar(m.content, m.role, false); });
      nodos.sugerencias.hidden = true;
    } else {
      bienvenida(false);
    }

    SUGERENCIAS.forEach(function (texto) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chat-chip';
      chip.textContent = texto;
      chip.addEventListener('click', function () { preguntar(texto); });
      nodos.sugerencias.appendChild(chip);
    });

    nodos.boton.addEventListener('click', function () { alternar(); });
    nodos.limpiar.addEventListener('click', limpiar);

    nodos.form.addEventListener('submit', function (evento) {
      evento.preventDefault();
      if (ocupado) { if (cancelar) cancelar(); return; }
      preguntar(nodos.caja.value);
    });

    nodos.caja.addEventListener('input', function () {
      nodos.caja.style.height = 'auto';
      nodos.caja.style.height = Math.min(nodos.caja.scrollHeight, 120) + 'px';
      refrescarBoton();
    });

    nodos.caja.addEventListener('keydown', function (evento) {
      if (evento.key === 'Enter' && !evento.shiftKey) {
        evento.preventDefault();
        preguntar(nodos.caja.value);
      }
    });

    document.addEventListener('keydown', function (evento) {
      if (evento.key === 'Escape' && abierto) {
        alternar(false);
        nodos.boton.focus();
      }
    });

    refrescarBoton();
    try {
      if (sessionStorage.getItem(ABIERTO) === '1') alternar(true);
    } catch (_) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
