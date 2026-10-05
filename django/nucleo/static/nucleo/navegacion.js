/*
 * Barra superior con menús desplegables y acciones comunes de la página.
 *
 * - Computadora (con mouse): el panel se abre al pasar el cursor y se cierra
 *   con un pequeño retardo al salir, para que no parpadee al moverse entre el
 *   botón y el panel. El clic también lo abre o lo cierra.
 * - Celular (sin cursor): el botón ☰ abre la hoja y cada grupo se abre con un
 *   toque, como un acordeón.
 * - Teclado: Enter o Espacio abre y cierra, flecha abajo entra a las pantallas,
 *   flechas arriba/abajo se mueven entre ellas y Esc cierra y vuelve al botón.
 */
(function () {
  'use strict';

  var RETARDO_CIERRE = 160;
  var conCursor = window.matchMedia('(hover: hover) and (pointer: fine) and (min-width: 901px)');

  var nav = document.querySelector('[data-nav]');
  if (!nav) return;

  var grupos = Array.prototype.slice.call(nav.querySelectorAll('[data-grupo]'));
  var hamburguesa = nav.querySelector('[data-hamburguesa]');
  var temporizador = null;

  function disparadorDe(grupo) {
    return grupo.querySelector('.nav-disparador');
  }

  function itemsDe(grupo) {
    return Array.prototype.slice.call(grupo.querySelectorAll('.nav-item'));
  }

  function abrir(grupo) {
    grupos.forEach(function (otro) {
      if (otro !== grupo) cerrar(otro);
    });
    grupo.classList.add('abierto');
    disparadorDe(grupo).setAttribute('aria-expanded', 'true');
  }

  function cerrar(grupo) {
    grupo.removeAttribute('data-por-cursor');
    grupo.classList.remove('abierto');
    disparadorDe(grupo).setAttribute('aria-expanded', 'false');
  }

  function cerrarTodos() {
    grupos.forEach(cerrar);
  }

  function cancelarCierre() {
    if (temporizador) {
      window.clearTimeout(temporizador);
      temporizador = null;
    }
  }

  function abrirHoja(abierta) {
    nav.classList.toggle('abierto', abierta);
    if (hamburguesa) {
      hamburguesa.setAttribute('aria-expanded', abierta ? 'true' : 'false');
      hamburguesa.setAttribute('aria-label', abierta ? 'Cerrar menú' : 'Abrir menú');
    }
    if (!abierta) cerrarTodos();
  }

  grupos.forEach(function (grupo) {
    var disparador = disparadorDe(grupo);

    // Cursor: abrir al entrar, cerrar con retardo al salir.
    grupo.addEventListener('mouseenter', function () {
      if (!conCursor.matches) return;
      cancelarCierre();
      if (!grupo.classList.contains('abierto')) grupo.setAttribute('data-por-cursor', '');
      abrir(grupo);
    });

    grupo.addEventListener('mouseleave', function () {
      if (!conCursor.matches) return;
      cancelarCierre();
      temporizador = window.setTimeout(function () {
        cerrar(grupo);
      }, RETARDO_CIERRE);
    });

    // Clic o toque: abre o cierra. Es la forma principal en un celular.
    // Si el panel ya se abrió con el cursor, el primer clic lo deja fijo en
    // vez de cerrarlo: así no desaparece justo cuando la persona hace clic.
    disparador.addEventListener('click', function () {
      if (grupo.hasAttribute('data-por-cursor')) {
        grupo.removeAttribute('data-por-cursor');
        abrir(grupo);
      } else if (grupo.classList.contains('abierto')) {
        cerrar(grupo);
      } else {
        abrir(grupo);
      }
    });

    disparador.addEventListener('keydown', function (evento) {
      if (evento.key === 'ArrowDown') {
        evento.preventDefault();
        abrir(grupo);
        var primero = itemsDe(grupo)[0];
        if (primero) window.setTimeout(function () { primero.focus(); }, 30);
      } else if (evento.key === 'Escape') {
        cerrar(grupo);
      }
    });

    grupo.addEventListener('keydown', function (evento) {
      var items = itemsDe(grupo);
      var indice = items.indexOf(document.activeElement);
      if (indice === -1) return;

      if (evento.key === 'ArrowDown') {
        evento.preventDefault();
        items[(indice + 1) % items.length].focus();
      } else if (evento.key === 'ArrowUp') {
        evento.preventDefault();
        items[(indice - 1 + items.length) % items.length].focus();
      } else if (evento.key === 'Home') {
        evento.preventDefault();
        items[0].focus();
      } else if (evento.key === 'End') {
        evento.preventDefault();
        items[items.length - 1].focus();
      } else if (evento.key === 'Escape') {
        evento.preventDefault();
        cerrar(grupo);
        disparador.focus();
      }
    });

    // Al salir con Tab del grupo, se cierra (solo en computadora).
    grupo.addEventListener('focusout', function (evento) {
      if (!conCursor.matches) return;
      if (!grupo.contains(evento.relatedTarget)) cerrar(grupo);
    });
  });

  if (hamburguesa) {
    hamburguesa.addEventListener('click', function () {
      abrirHoja(!nav.classList.contains('abierto'));
    });
  }

  // Clic fuera de la barra: cierra todo.
  document.addEventListener('click', function (evento) {
    if (!nav.contains(evento.target)) {
      cerrarTodos();
      abrirHoja(false);
    }
  });

  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape' && nav.classList.contains('abierto')) {
      abrirHoja(false);
      if (hamburguesa) hamburguesa.focus();
    }
  });

  // Al pasar de celular a computadora (o al revés), no dejar nada abierto.
  var alCambiar = function () {
    abrirHoja(false);
  };
  if (conCursor.addEventListener) {
    conCursor.addEventListener('change', alCambiar);
  } else if (conCursor.addListener) {
    conCursor.addListener(alCambiar);
  }

  // Confirmación antes de borrar: los formularios traen data-confirmar.
  document.querySelectorAll('form[data-confirmar]').forEach(function (formulario) {
    formulario.addEventListener('submit', function (evento) {
      if (!window.confirm(formulario.getAttribute('data-confirmar'))) {
        evento.preventDefault();
      }
    });
  });
})();
