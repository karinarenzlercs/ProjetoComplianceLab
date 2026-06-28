/* =========================================================================
 * app.js — Lógica do front-end do dossiê (Compliance Lab / Diagnóstico LGPD).
 *
 * Dirige as etapas do fluxo e conversa com o backend Flask (server.py), que
 * por sua vez usa o motor de regras determinístico, a redação e o gerador de
 * PDF — tudo já existente e inalterado.
 *
 *   intro  -> identificação (capa + GRC + formulário, renderizados no HTML)
 *   quiz   -> questionário do setor (perguntas vindas do JSON real, 4 opções)
 *   report -> animação de compilação + score/risco reais + download do PDF
 * ========================================================================= */

(function () {
  "use strict";

  // -- paleta (mesma do design) --------------------------------------------
  var TINTA = "#1A1714", PAPEL = "#F5F2EC", VERMELHO = "#B0202A", CINZA = "#8A847A";

  // Modelo de negócio do design -> setor interno do backend.
  var MODELOS = [
    { id: "juridico",   code: "M—01", title: "Escritório de Advocacia", desc: "Sigilo profissional e dados sensíveis de clientes." },
    { id: "tecnologia", code: "M—02", title: "Tecnologia ou SaaS",      desc: "Operador de dados em escala, contratos e APIs." },
    { id: "ecommerce",  code: "M—03", title: "E-commerce",              desc: "Alto volume de titulares, pagamento e marketing." },
  ];

  // Selo (código) de cada opção, por texto exato vindo do questionário.
  var CODIGO_OPCAO = {
    "Sim, implementado": "+2",
    "Parcialmente": "+1",
    "Não": "00",
    "Não se aplica": "N/A",
  };

  // Frase de contexto por nível de maturidade.
  var DESC_NIVEL = {
    "Inicial": "Estágio inicial: controles ainda incipientes e lacunas relevantes que expõem a empresa. Há bastante a estruturar.",
    "Em Desenvolvimento": "Em desenvolvimento: alguns controles já existem, mas há lacunas importantes a fechar para reduzir o risco.",
    "Intermediário": "Bases sólidas em algumas dimensões, com lacunas relevantes que ainda expõem a empresa. Há caminho claro para a adequação.",
    "Avançado": "Maturidade avançada: controles bem estabelecidos. O foco passa a ser melhoria contínua e evidências.",
    "Não avaliável": "Não foi possível avaliar: a maioria das perguntas foi marcada como \"Não se aplica\".",
  };

  var STATUS = [
    "Validando respostas e identificação da empresa",
    "Cruzando respostas com a base normativa (LGPD · ANPD)",
    "Calculando score de maturidade por dimensão",
    "Identificando lacunas por nível de risco",
    "Priorizando plano de ação",
    "Compilando dossiê final",
  ];

  // -- estado --------------------------------------------------------------
  var estado = {
    setor: null,
    empresa: "",
    setorNome: "",
    perguntas: [],
    respostas: {},   // { pergunta_id: texto_da_resposta }
    idx: 0,
    resultado: null, // resposta do /api/diagnostico
  };

  function $(sel, raiz) { return (raiz || document).querySelector(sel); }
  function pad(n) { return String(n).padStart(2, "0"); }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ========================================================================
  // ETAPA 0 — animações da página inicial (reveal + count-up)
  // ========================================================================

  function ativarReveal() {
    var alvos = document.querySelectorAll("[data-reveal]");
    if (!("IntersectionObserver" in window)) {
      alvos.forEach(function (n) { n.classList.add("cl-in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("cl-in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });
    alvos.forEach(function (n) { io.observe(n); });
  }

  function ativarContadores() {
    var alvos = document.querySelectorAll("[data-count-to]");
    if (!("IntersectionObserver" in window)) {
      alvos.forEach(function (n) { n.textContent = n.getAttribute("data-count-to"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !e.target.__contado) {
          e.target.__contado = true;
          animarContagem(e.target);
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.6 });
    alvos.forEach(function (n) { io.observe(n); });
  }

  function animarContagem(el) {
    var alvo = parseFloat(el.getAttribute("data-count-to")) || 0;
    var dur = 1600, ini = performance.now();
    var ease = function (t) { return 1 - Math.pow(1 - t, 3); };
    function passo(agora) {
      var p = Math.min(1, (agora - ini) / dur);
      el.textContent = Math.round(alvo * ease(p));
      if (p < 1) requestAnimationFrame(passo);
    }
    requestAnimationFrame(passo);
  }

  // ========================================================================
  // ETAPA 1 — identificação (nome + modelo de negócio)
  // ========================================================================

  function montarModelos() {
    var box = $("#cl-modelos");
    box.innerHTML = MODELOS.map(function (m) {
      return (
        '<div class="cl-modelo" data-id="' + m.id + '" role="button" tabindex="0" ' +
        'style="display:flex; flex-direction:column; min-height:172px; padding:22px 20px; cursor:pointer; user-select:none; background:transparent; border:1px solid rgba(26,23,20,0.22); transition:border-color .25s, background .25s;">' +
          '<div style="display:flex; justify-content:space-between; align-items:center;">' +
            '<span class="cl-modelo-code" style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.12em; color:' + CINZA + ';">' + m.code + '</span>' +
            '<span class="cl-modelo-dot" style="display:inline-block; width:9px; height:9px; background:transparent; border:1px solid rgba(26,23,20,0.3); transition:all .25s;"></span>' +
          '</div>' +
          '<div style="font-weight:700; font-size:19px; line-height:1.15; letter-spacing:-0.01em; margin-top:34px;">' + esc(m.title) + '</div>' +
          '<div style="font-size:13px; line-height:1.45; color:#6A645B; margin-top:8px;">' + esc(m.desc) + '</div>' +
        '</div>'
      );
    }).join("");

    Array.prototype.forEach.call(box.querySelectorAll(".cl-modelo"), function (card) {
      function escolher() { selecionarModelo(card.getAttribute("data-id")); }
      card.addEventListener("click", escolher);
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); escolher(); }
      });
    });
  }

  function selecionarModelo(id) {
    estado.setor = id;
    var m = MODELOS.find(function (x) { return x.id === id; });
    estado.setorNome = m ? m.title : "";
    Array.prototype.forEach.call(document.querySelectorAll(".cl-modelo"), function (card) {
      var on = card.getAttribute("data-id") === id;
      card.style.borderColor = on ? VERMELHO : "rgba(26,23,20,0.22)";
      card.style.background = on ? "rgba(176,32,42,0.05)" : "transparent";
      $(".cl-modelo-code", card).style.color = on ? VERMELHO : CINZA;
      var dot = $(".cl-modelo-dot", card);
      dot.style.background = on ? VERMELHO : "transparent";
      dot.style.borderColor = on ? VERMELHO : "rgba(26,23,20,0.3)";
    });
    atualizarIniciar();
  }

  function estiloBotaoPrincipal(ativo) {
    return [
      "display:inline-flex", "align-items:center", "font-family:'IBM Plex Mono',monospace",
      "font-size:12px", "letter-spacing:0.14em", "text-transform:uppercase", "font-weight:500",
      "padding:18px 30px", "border:0", "cursor:" + (ativo ? "pointer" : "not-allowed"),
      "background:" + (ativo ? TINTA : "rgba(26,23,20,0.12)"),
      "color:" + (ativo ? PAPEL : CINZA),
      "transition:background .25s, color .25s",
    ].join(";");
  }

  function atualizarIniciar() {
    var pronto = estado.empresa.trim().length > 0 && !!estado.setor;
    var btn = $("#cl-iniciar");
    btn.style.cssText = estiloBotaoPrincipal(pronto);
    btn.disabled = !pronto;
    $("#cl-iniciar-hint").textContent = pronto ? "Pronto" : "Preencha os dois campos";
  }

  function ligarIdentificacao() {
    montarModelos();
    var inp = $("#cl-empresa");
    inp.addEventListener("input", function () { estado.empresa = inp.value; atualizarIniciar(); });
    inp.addEventListener("focus", function () { inp.style.borderBottomColor = VERMELHO; });
    inp.addEventListener("blur", function () { inp.style.borderBottomColor = "rgba(26,23,20,0.32)"; });
    $("#cl-iniciar").addEventListener("click", iniciarDiagnostico);
    atualizarIniciar();
  }

  // ========================================================================
  // ETAPA 2 — questionário
  // ========================================================================

  function barraDossie(empresa, modelo, status) {
    return (
      '<div style="position:sticky; top:0; background:' + PAPEL + '; z-index:5;">' +
        '<div style="display:flex; justify-content:space-between; align-items:center; padding:22px 40px; font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.12em; text-transform:uppercase;">' +
          '<div style="display:flex; align-items:center; gap:12px; min-width:0;">' +
            '<span style="display:inline-block; width:9px; height:9px; background:' + VERMELHO + '; flex-shrink:0;"></span>' +
            '<span style="font-weight:600; color:' + TINTA + '; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">' + esc(empresa) + '</span>' +
            '<span style="color:' + CINZA + '; white-space:nowrap;">· ' + esc(modelo) + '</span>' +
          '</div>' +
          '<div style="color:' + CINZA + '; white-space:nowrap;">Dossiê Nº LGPD—001 · ' + esc(status) + '</div>' +
        '</div>' +
        '<div style="height:1px; background:' + TINTA + '; opacity:0.16; margin:0 40px;"></div>' +
      '</div>'
    );
  }

  function iniciarDiagnostico() {
    if (!estado.empresa.trim() || !estado.setor) return;
    estado.empresa = estado.empresa.trim();

    var quiz = $("#cl-quiz");
    quiz.innerHTML = barraDossie(estado.empresa, estado.setorNome, "Carregando") +
      '<div style="max-width:1320px; margin:0 auto; padding:80px 40px; font-family:\'IBM Plex Mono\',monospace; font-size:13px; letter-spacing:0.06em; color:' + CINZA + ';">Carregando questionário…</div>';
    mostrarOverlay(quiz);

    fetch("/api/questionario/" + encodeURIComponent(estado.setor))
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (data) {
        estado.perguntas = data.perguntas || [];
        estado.setorNome = data.setor_nome || estado.setorNome;
        estado.respostas = {};
        estado.idx = 0;
        montarQuiz();
      })
      .catch(function (e) {
        quiz.innerHTML = barraDossie(estado.empresa, estado.setorNome, "Erro") +
          '<div style="max-width:1320px; margin:0 auto; padding:80px 40px; color:' + VERMELHO + '; font-size:18px;">Não foi possível carregar o questionário. ' + esc(e.message) + '</div>';
      });
  }

  function montarQuiz() {
    var quiz = $("#cl-quiz");
    quiz.innerHTML =
      barraDossie(estado.empresa, estado.setorNome, "Em andamento") +
      '<div style="max-width:1320px; margin:0 auto; padding:54px 40px 80px;">' +
        '<div style="display:flex; align-items:center; gap:18px; margin-bottom:56px;">' +
          '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:12px; font-weight:600; letter-spacing:0.16em; color:' + VERMELHO + ';">04</span>' +
          '<span style="height:1px; width:60px; background:' + VERMELHO + '; opacity:0.6;"></span>' +
          '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.22em; text-transform:uppercase; color:' + CINZA + ';">Questionário de maturidade</span>' +
        '</div>' +
        '<div style="border-top:1px solid ' + TINTA + '; padding-top:30px;">' +
          '<div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:54px;">' +
            '<span id="cl-q-dim" style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.18em; text-transform:uppercase; color:' + VERMELHO + ';"></span>' +
            '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:14px; letter-spacing:0.1em; color:' + TINTA + ';"><span id="cl-q-idx"></span> <span style="color:' + CINZA + ';">/ <span id="cl-q-total"></span></span></span>' +
          '</div>' +
          '<div id="cl-q-body"></div>' +
          '<div style="margin-top:64px;"><div style="position:relative; height:2px; background:rgba(26,23,20,0.14);"><div id="cl-q-prog" style="position:absolute; top:0; left:0; height:2px; background:' + VERMELHO + '; width:0; transition:width .4s ease;"></div></div></div>' +
          '<div style="display:flex; justify-content:space-between; align-items:center; margin-top:24px;">' +
            '<button id="cl-back" type="button">← Voltar</button>' +
            '<span id="cl-navhint" style="font-family:\'IBM Plex Mono\',monospace; font-size:10px; letter-spacing:0.12em; text-transform:uppercase; color:' + CINZA + ';"></span>' +
            '<button id="cl-next" type="button"></button>' +
          '</div>' +
        '</div>' +
      '</div>';

    $("#cl-q-total").textContent = pad(estado.perguntas.length);
    $("#cl-back").addEventListener("click", function () { navegar(-1); });
    $("#cl-next").addEventListener("click", function () { navegar(1); });
    renderPergunta();
  }

  function renderPergunta() {
    var i = estado.idx, p = estado.perguntas[i], total = estado.perguntas.length;
    var resp = estado.respostas[p.id] || null;

    $("#cl-q-dim").textContent = p.dimensao || "";
    $("#cl-q-idx").textContent = pad(i + 1);
    $("#cl-q-prog").style.width = (((i + 1) / total) * 100) + "%";

    var opcoesHTML = (p.opcoes || []).map(function (op) {
      var on = resp === op;
      var code = CODIGO_OPCAO[op] || "";
      return (
        '<button type="button" class="cl-opt" data-op="' + esc(op) + '" ' +
        'style="display:flex; align-items:center; gap:16px; width:100%; text-align:left; padding:18px 20px; cursor:pointer; background:' + (on ? "rgba(176,32,42,0.05)" : "transparent") + '; border:1px solid ' + (on ? VERMELHO : "rgba(26,23,20,0.22)") + '; transition:border-color .2s, background .2s;">' +
          '<span style="display:inline-block; width:11px; height:11px; flex-shrink:0; border-radius:50%; background:' + (on ? VERMELHO : "transparent") + '; border:1px solid ' + (on ? VERMELHO : "rgba(26,23,20,0.34)") + ';"></span>' +
          '<span style="font-weight:600; font-size:18px; letter-spacing:-0.01em;">' + esc(op) + '</span>' +
          '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.1em; margin-left:auto; color:' + (on ? VERMELHO : CINZA) + ';">' + esc(code) + '</span>' +
        '</button>'
      );
    }).join("");

    var tipHTML = p.exemplo
      ? '<div style="display:flex; gap:12px; margin-top:30px; max-width:52ch;">' +
          '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.1em; color:' + VERMELHO + '; flex-shrink:0;">NOTA</span>' +
          '<p style="font-family:\'IBM Plex Mono\',monospace; font-size:12px; line-height:1.6; color:' + VERMELHO + '; margin:0; opacity:0.85;">' + esc(p.exemplo) + '</p>' +
        '</div>'
      : "";

    $("#cl-q-body").innerHTML =
      '<div style="display:grid; grid-template-columns:minmax(0,1.15fr) minmax(0,0.85fr); gap:80px; align-items:start;">' +
        '<div>' +
          '<div style="font-family:\'IBM Plex Mono\',monospace; font-size:clamp(40px,5vw,76px); font-weight:500; line-height:1; letter-spacing:-0.02em; color:rgba(26,23,20,0.18); margin-bottom:28px;">' + pad(i + 1) + '</div>' +
          '<h2 style="font-weight:800; font-size:clamp(26px,3.4vw,46px); line-height:1.08; letter-spacing:-0.02em; margin:0;">' + esc(p.pergunta) + '</h2>' +
          tipHTML +
        '</div>' +
        '<div style="display:flex; flex-direction:column; gap:12px; padding-top:8px;">' + opcoesHTML + '</div>' +
      '</div>';

    Array.prototype.forEach.call($("#cl-q-body").querySelectorAll(".cl-opt"), function (btn) {
      btn.addEventListener("click", function () {
        estado.respostas[p.id] = btn.getAttribute("data-op");
        renderPergunta();
      });
    });

    // botões de navegação
    var primeiro = i === 0, ultimo = i === total - 1, pode = !!resp;
    var back = $("#cl-back");
    back.style.cssText = [
      "font-family:'IBM Plex Mono',monospace", "font-size:11px", "letter-spacing:0.12em", "text-transform:uppercase",
      "background:transparent", "border:0", "padding:8px 0",
      "color:" + (primeiro ? "rgba(26,23,20,0.25)" : TINTA),
      "cursor:" + (primeiro ? "not-allowed" : "pointer"),
    ].join(";");
    back.disabled = primeiro;

    var next = $("#cl-next");
    next.innerHTML = (ultimo ? "Gerar relatório" : "Avançar") + ' <span style="margin-left:12px;">→</span>';
    next.style.cssText = [
      "display:inline-flex", "align-items:center", "font-family:'IBM Plex Mono',monospace",
      "font-size:12px", "letter-spacing:0.14em", "text-transform:uppercase", "font-weight:500",
      "padding:16px 28px", "border:0", "cursor:" + (pode ? "pointer" : "not-allowed"),
      "background:" + (pode ? TINTA : "rgba(26,23,20,0.12)"),
      "color:" + (pode ? PAPEL : CINZA),
      "transition:background .25s, color .25s",
    ].join(";");
    next.disabled = !pode;
    $("#cl-navhint").textContent = pode ? "" : "Selecione uma resposta";
  }

  function navegar(dir) {
    var ni = estado.idx + dir;
    if (ni < 0) return;
    if (!estado.respostas[estado.perguntas[estado.idx].id] && dir > 0) return;
    if (ni >= estado.perguntas.length) { enviarDiagnostico(); return; }

    var body = $("#cl-q-body");
    body.style.transition = "opacity .25s ease, transform .25s ease";
    body.style.opacity = "0";
    body.style.transform = dir > 0 ? "translateY(-12px)" : "translateY(12px)";
    setTimeout(function () {
      estado.idx = ni;
      renderPergunta();
      var nb = $("#cl-q-body");
      nb.style.transition = "none";
      nb.style.opacity = "0";
      nb.style.transform = "translateY(10px)";
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          nb.style.transition = "opacity .4s ease, transform .4s ease";
          nb.style.opacity = "1";
          nb.style.transform = "translateY(0)";
        });
      });
    }, 220);
  }

  // ========================================================================
  // ETAPA 3 — relatório (compilação + resultado)
  // ========================================================================

  function enviarDiagnostico() {
    var rep = $("#cl-report");
    rep.innerHTML =
      barraDossie(estado.empresa, estado.setorNome, "Confidencial") +
      '<div style="max-width:1320px; margin:0 auto; padding:54px 40px 90px;">' +
        cabecalhoSecao("05", "Geração do relatório") +
        '<div style="max-width:760px; margin:60px 0;">' +
          '<div style="font-weight:800; font-size:clamp(30px,4vw,52px); line-height:1.05; letter-spacing:-0.02em; margin:0 0 48px;">Compilando o dossiê<span style="color:' + VERMELHO + ';">.</span></div>' +
          '<div id="cl-status"></div>' +
        '</div>' +
      '</div>';
    esconderOverlay($("#cl-quiz"));
    mostrarOverlay(rep);

    animarStatus();

    fetch("/api/diagnostico", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setor: estado.setor, empresa: estado.empresa, respostas: estado.respostas }),
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.body.erro || "Falha ao gerar o diagnóstico.");
        estado.resultado = res.body;
        // garante que a animação rode pelo menos até o fim antes de revelar
        var espera = Math.max(0, statusFim - Date.now());
        setTimeout(mostrarRelatorio, espera + 400);
      })
      .catch(function (e) {
        $("#cl-status").insertAdjacentHTML("beforeend",
          '<div style="margin-top:28px; color:' + VERMELHO + '; font-size:16px;">Erro: ' + esc(e.message) + '</div>');
      });
  }

  var statusFim = 0;
  function animarStatus() {
    var box = $("#cl-status");
    box.innerHTML = STATUS.map(function (linha, i) {
      return (
        '<div class="cl-status-row" style="display:flex; align-items:baseline; gap:18px; padding:11px 0; border-bottom:1px solid rgba(26,23,20,0.10); opacity:0; transform:translateY(6px); transition:opacity .5s ease, transform .5s ease;">' +
          '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; color:' + VERMELHO + '; letter-spacing:0.1em;">' + pad(i + 1) + '</span>' +
          '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:13px; letter-spacing:0.04em; color:' + TINTA + '; flex:1;">' + esc(linha) + '</span>' +
          '<span class="cl-status-ok" style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.12em; text-transform:uppercase; color:' + CINZA + '; opacity:0;">OK</span>' +
        '</div>'
      );
    }).join("");

    var linhas = box.querySelectorAll(".cl-status-row");
    var passo = 650;
    statusFim = Date.now() + linhas.length * passo;
    linhas.forEach(function (row, i) {
      setTimeout(function () {
        row.style.opacity = "1";
        row.style.transform = "translateY(0)";
        $(".cl-status-ok", row).style.opacity = "1";
      }, i * passo);
    });
  }

  function cabecalhoSecao(num, titulo) {
    return (
      '<div style="display:flex; align-items:center; gap:18px; margin-bottom:48px;">' +
        '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:12px; font-weight:600; letter-spacing:0.16em; color:' + VERMELHO + ';">' + num + '</span>' +
        '<span style="height:1px; width:60px; background:' + VERMELHO + '; opacity:0.6;"></span>' +
        '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.22em; text-transform:uppercase; color:' + CINZA + ';">' + esc(titulo) + '</span>' +
      '</div>'
    );
  }

  function mostrarRelatorio() {
    var d = estado.resultado;
    var score = Math.round(d.score || 0);
    var rr = d.resumo_risco || { alto: 0, medio: 0, baixo: 0 };
    var desc = DESC_NIVEL[d.nivel] || "";

    var avisoHTML = "";
    if (d.fonte_redacao === "fallback" && d.aviso_redacao) {
      avisoHTML = '<div style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.04em; color:' + CINZA + '; border-left:2px solid ' + CINZA + '; padding:8px 14px; margin-bottom:40px;">' + esc(d.aviso_redacao) + '</div>';
    }

    var rep = $("#cl-report");
    rep.innerHTML =
      barraDossie(d.empresa, estado.setorNome, "Confidencial") +
      '<div style="max-width:1320px; margin:0 auto; padding:54px 40px 90px;">' +
        cabecalhoSecao("05", "Relatório de maturidade") +
        avisoHTML +
        '<div style="display:flex; justify-content:space-between; align-items:flex-start; border-top:1px solid ' + TINTA + '; padding-top:18px; margin-bottom:60px; font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.14em; text-transform:uppercase; color:' + CINZA + ';">' +
          '<span>' + esc(d.setor_nome || estado.setorNome) + ' · LGPD / GRC</span>' +
          '<span style="border:1px solid ' + VERMELHO + '; color:' + VERMELHO + '; padding:5px 10px;">Prévia</span>' +
        '</div>' +

        // score hero
        '<div style="display:grid; grid-template-columns:minmax(0,1.25fr) minmax(0,0.75fr); gap:70px; align-items:end; margin-bottom:80px;">' +
          '<div>' +
            '<div style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.16em; text-transform:uppercase; color:' + CINZA + '; margin-bottom:18px;">Score de maturidade</div>' +
            '<div style="display:flex; align-items:baseline; gap:4px;">' +
              '<span style="font-weight:900; font-size:clamp(120px,20vw,300px); line-height:0.82; letter-spacing:-0.04em; color:' + TINTA + ';">' + score + '</span>' +
              '<span style="font-weight:800; font-size:clamp(28px,4vw,56px); color:' + CINZA + '; letter-spacing:-0.02em;">/100</span>' +
            '</div>' +
          '</div>' +
          '<div style="padding-bottom:14px;">' +
            '<div style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.16em; text-transform:uppercase; color:' + VERMELHO + '; margin-bottom:12px;">Nível classificado</div>' +
            '<div style="font-weight:800; font-size:clamp(28px,3.6vw,46px); letter-spacing:-0.02em; line-height:1; margin-bottom:18px;">' + esc(d.nivel) + '</div>' +
            '<p style="font-size:15px; line-height:1.55; color:#3A352E; margin:0;">' + esc(desc) + '</p>' +
          '</div>' +
        '</div>' +

        // lacunas por risco
        '<div style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.16em; text-transform:uppercase; color:' + CINZA + '; margin-bottom:22px;">Lacunas identificadas por nível de risco</div>' +
        '<div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0; border-top:1px solid ' + TINTA + '; margin-bottom:80px;">' +
          blocoRisco("#B0202A", "Risco alto", rr.alto, "lacunas exigem ação imediata", true) +
          blocoRisco("#C2891B", "Risco médio", rr.medio, "lacunas para o plano de 90 dias", true) +
          blocoRisco("#3E7C5A", "Risco baixo", rr.baixo, "ajustes de melhoria contínua", false) +
        '</div>' +

        // CTA download
        '<div style="display:grid; grid-template-columns:minmax(0,1fr) auto; gap:40px; align-items:center; border-top:1px solid ' + TINTA + '; padding-top:40px;">' +
          '<div>' +
            '<div style="font-weight:800; font-size:clamp(22px,2.4vw,32px); letter-spacing:-0.02em; line-height:1.1; margin-bottom:10px;">Dossiê completo, com plano de ação priorizado.</div>' +
            '<p style="font-size:15px; line-height:1.55; color:#3A352E; margin:0; max-width:52ch;">' + d.total_lacunas + ' lacuna(s) detalhada(s), com base normativa, descrição do risco e passo a passo de adequação.</p>' +
          '</div>' +
          (d.pdf_disponivel
            ? '<button id="cl-download" type="button" style="display:inline-flex; align-items:center; gap:14px; font-family:\'IBM Plex Mono\',monospace; font-size:12px; letter-spacing:0.14em; text-transform:uppercase; font-weight:600; padding:20px 34px; border:0; cursor:pointer; background:' + VERMELHO + '; color:' + PAPEL + ';">Baixar relatório (PDF) <span>↓</span></button>'
            : '<div style="max-width:320px; font-family:\'IBM Plex Mono\',monospace; font-size:11px; line-height:1.6; letter-spacing:0.04em; color:' + CINZA + '; border:1px solid rgba(26,23,20,0.2); padding:16px 18px;">' + esc(d.pdf_erro || "PDF indisponível no momento.") + '</div>') +
        '</div>' +

        // recomeçar
        '<div style="margin-top:48px; border-top:1px solid rgba(26,23,20,0.16); padding-top:24px;">' +
          '<button id="cl-restart" type="button" style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.12em; text-transform:uppercase; background:transparent; border:0; color:' + CINZA + '; cursor:pointer;">↺ Fazer um novo diagnóstico</button>' +
        '</div>' +

        // reveal wrapper end
      '</div>';

    // animação de entrada
    var alvo = rep.querySelector('div[style*="max-width:1320px"]');
    if (alvo) {
      alvo.style.opacity = "0";
      alvo.style.transform = "translateY(22px)";
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          alvo.style.transition = "opacity .8s ease, transform .8s ease";
          alvo.style.opacity = "1";
          alvo.style.transform = "translateY(0)";
        });
      });
    }

    var btnDl = $("#cl-download");
    if (btnDl) {
      btnDl.addEventListener("click", function () {
        window.location.href = "/api/relatorio/" + encodeURIComponent(d.id);
      });
    }
    $("#cl-restart").addEventListener("click", reiniciar);
  }

  function blocoRisco(cor, rotulo, valor, legenda, borda) {
    var pad = borda ? "32px 36px" : "32px 0 32px 36px";
    if (rotulo === "Risco alto") pad = "32px 36px 32px 0";
    return (
      '<div style="padding:' + pad + ';' + (borda ? " border-right:1px solid rgba(26,23,20,0.14);" : "") + '">' +
        '<div style="display:flex; align-items:center; gap:10px; margin-bottom:22px;">' +
          '<span style="width:11px; height:11px; background:' + cor + '; display:inline-block;"></span>' +
          '<span style="font-family:\'IBM Plex Mono\',monospace; font-size:11px; letter-spacing:0.14em; text-transform:uppercase; color:' + cor + ';">' + rotulo + '</span>' +
        '</div>' +
        '<div style="font-weight:900; font-size:clamp(56px,7vw,92px); line-height:0.9; letter-spacing:-0.03em;">' + (valor || 0) + '</div>' +
        '<div style="font-size:14px; color:#6A645B; margin-top:10px;">' + esc(legenda) + '</div>' +
      '</div>'
    );
  }

  function reiniciar() {
    esconderOverlay($("#cl-report"));
    estado.respostas = {};
    estado.idx = 0;
    estado.resultado = null;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ========================================================================
  // utilidades de overlay
  // ========================================================================

  function mostrarOverlay(el) {
    el.classList.add("cl-show");
    document.body.style.overflow = "hidden";
    el.scrollTop = 0;
    window.scrollTo({ top: 0 });
  }
  function esconderOverlay(el) {
    el.classList.remove("cl-show");
    if (!$("#cl-quiz").classList.contains("cl-show") && !$("#cl-report").classList.contains("cl-show")) {
      document.body.style.overflow = "";
    }
  }

  // ========================================================================
  // boot
  // ========================================================================

  document.addEventListener("DOMContentLoaded", function () {
    ativarReveal();
    ativarContadores();
    ligarIdentificacao();
  });
})();
