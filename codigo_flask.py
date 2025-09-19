    async def speak(text: str, interruptible: bool = True):
        await ws.send_json({"type": "text", "token": text, "last": True, "interruptible": bool(interruptible)})
        try:
            import asyncio
            await asyncio.sleep(int(_env("SPEAK_SLEEP_MS", "0")) / 1000.0)
        except Exception:
            pass

    def _norm(t: str) -> str:
        return re.sub(r"\s+", " ", (t or "").strip())

    def _dup_user(t: str) -> bool:
        t = _norm(t).lower()
        now = _now_ms()
        if session["last_user"] == t and (now - session["last_user_ts"]) < 1200:
            return True
        session["last_user"] = t
        session["last_user_ts"] = now
        return False

    async def ask_once(step_key: str):
        now = _now_ms()
        if session["last_q"] == step_key and (now - session["last_q_ts"]) < 1200:
            return
        session["last_q"] = step_key
        session["last_q_ts"] = now
        prompts = {
            "role": "Para atenderle: ¿Es usted propietario o inquilino?",
            "city": "¿En qué población está interesado?",
            "zone": "¿Qué zona o barrio?",
            "name": "¿Su nombre completo?",
            "phone": "¿Su teléfono de contacto, por favor?",
            "post": "¿Desea más información o ayuda?",
        }
        await speak(prompts.get(step_key, ""))

    async def answer_topic(topic: str):
        idx = session["info_hits"].get(topic, 0)
        answers = KNOWLEDGE[topic]["answers"]
        text = answers[idx % len(answers)]
        session["info_hits"][topic] = idx + 1
        await speak(text)

    async def finish():
        lead = session["lead"].copy()
        await speak("Gracias. Tomamos sus datos. Le contactaremos en breve.", interruptible=False)
        print("<<LEAD>>" + json.dumps(lead, ensure_ascii=False) + "<<END>>", flush=True)
        # cerrar conversación (no bucles)
        session["step"] = "done"
        session["ended"] = True
        try:
            await speak("Hasta luego.")
        except Exception:
            pass

    async def handle_text(user_text: str):
        if _dup_user(user_text):
            return
        t  = _norm(user_text)
        tl = t.lower()
        s  = session["step"]
        lead = session["lead"]

        # ya terminó
        if session.get("ended"):
            return

        # ayuda explícita
        if _is_yes_help(tl):
            if not lead.get("nombre"):
                session["step"] = "name"
                await speak("Perfecto. Antes, ¿su nombre completo, por favor?")
                return
            if not lead.get("telefono"):
                session["step"] = "phone"
                await speak("De acuerdo. ¿Su teléfono de contacto?")
                return
            await speak(f"De acuerdo. Un asesor le llamará al {lead['telefono']} en breve.")
            session["step"] = "post"
            await ask_once("post")
            return

        # si da muchos dígitos fuera de 'phone', reconducimos
        if s != "phone":
            only_digits = _digits(t)
            if len(only_digits) >= 7:
                if not lead.get("nombre"):
                    session["step"] = "name"
                    await speak("Tomamos nota, pero primero necesito su nombre completo, por favor.")
                    return
                session["step"] = "phone"
                await speak("Ahora sí, ¿su teléfono de contacto, por favor?")
                return

        # flujo por pasos
        if s == "role":
            if _role_owner(tl):
                lead["role"] = "propietario"
                session["step"] = "city"
                await speak("Gracias.")
                await ask_once("city")
                return
            if _role_tenant(tl):
                lead["role"] = "inquilino"
                session["step"] = "city"
                await speak("Gracias.")
                await ask_once("city")
                return
            await ask_once("role")
            return

        elif s == "city":
            if len(tl) >= 2:
                lead["poblacion"] = t.title()
                session["step"] = "zone"
                await ask_once("zone")
                return
            await ask_once("city")
            return

        elif s == "zone":
            if len(tl) >= 2:
                lead["zona"] = t.title()
                session["step"] = "name"
                await ask_once("name")
                return
            await ask_once("zone")
            return

        elif s == "name":
            if len(t.split()) >= 2:
                lead["nombre"] = t
                session["step"] = "phone"
                await ask_once("phone")
                return
            await speak("¿Su nombre completo, por favor?")
            return

        elif s == "phone":
            d = _digits(t)
            if d.startswith("34") and len(d) >= 11:
                d = d[-9:]
            if len(d) == 9 and d[0] in "6789":
                lead["telefono"] = d
                await finish()
                return
            await speak("¿Me facilita un teléfono de nueve dígitos?")
            return

        elif s == "post":
            tlsp = f" {tl} "
            if any(w in tlsp for w in [" no ", " gracias ", " adios ", " adiós ", " hasta luego "]):
                session["step"] = "done"
                session["ended"] = True
                await speak("De acuerdo. Gracias, hasta luego.")
                return
            if session.get("last_q") != "post":
                await ask_once("post")
            return

        elif s == "await_setup":
            session["step"] = "role"
            await ask_once("role")
            return

        # conocimiento SOLO fuera del flujo
        topic = _match_topic(tl, s)
        if topic:
            await answer_topic(topic)
            if session["step"] != "await_setup":
                await ask_once(session["step"])
            return

        await ask_once(session["step"])

    try:
        while True:
            msg = await ws.receive_json()
            tp = msg.get("type")
            if tp == "setup":
                if session.get("last_q") != "role":
                    session["step"] = "role"
                    await ask_once("role")
            elif tp == "prompt":
                txt = msg.get("voicePrompt", "") or ""
                if msg.get("last", True) and txt:
                    await handle_text(txt)
            elif tp == "interrupt":
                await ask_once(session["step"])
            elif tp == "dtmf":
                pass
            elif tp == "error":
                await speak("Disculpe. Estamos teniendo problemas. Inténtelo más tarde.", interruptible=False)
                break
    except Exception as e:
        print("CR ws error:", e, flush=True)
    finally:
        with contextlib.suppress(Exception):
            await ws.close()

@app.post("/assign")
async def assign(payload: dict):
    zone_key = f"{(payload.get('poblacion') or '').strip().lower()}-{(payload.get('zona') or '').strip().lower()}"
    fid = hashlib.sha1(zone_key.encode("utf-8")).hexdigest()[:10]
    task = {
        "title": "Contactar lead",
        "zone_key": zone_key,
        "franchisee_id": fid,
        "lead": payload,
        "created_at": int(time.time()),
    }
    return JSONResponse({"ok": True, "task": task})
