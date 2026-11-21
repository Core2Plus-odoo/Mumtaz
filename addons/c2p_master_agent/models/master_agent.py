import json, logging, urllib.request
from datetime import datetime, timedelta
from odoo import fields, models
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

C2P_KNOWLEDGE = """
COMPANY: C2P Consultants FZC LLC — Official Odoo Ready Partner, UAE (Ajman Free Zone)
ENTITIES: Consultants FZC (UAE/AED/5%VAT) | Core 2 Plus Karachi (branch) | C2P Solutions (Pakistan/PKR/SRB13%)
INTERCOMPANY: 60% Consultants / 40% Solutions revenue split

SERVICES & PRICING:
- Odoo ERP Implementation v15-v19: AED 8,000-80,000 fixed price
- Custom BI/Dashboards, AI Systems, Web/eCommerce, Oracle APEX
- UAE VAT / KSA ZATCA compliance consulting
- AMC: Basic AED 1,200/mo (8hrs) | Standard AED 2,000/mo (16hrs)
- Mumtaz SaaS: AED 499/mo Starter | AED 999/mo Business
- Payment: 50% on signature, 30% on UAT, 20% on go-live

METHODOLOGY (8 phases, 6-8 weeks):
Phase 1 BRD (1wk) → Phase 2 Design (1wk) → Phase 3 Config (2wks) → Phase 4 Data Migration (1wk)
→ Phase 5 Training (1wk) → Phase 6 UAT (1wk) → Phase 7 Go-Live (3 days) → Phase 8 Hypercare (2wks)

TEAM ROLES & TASK ROUTING:
Muhammad Umer — Founder/Principal: all major decisions, client escalations, proposals
Shafat — CTO: all tech decisions, Python/DB/DevOps/AI/deployment/architecture
Muhammad Bilal — Client Success: ALL qualified leads, discovery calls, client communication
Kamran Ali — PM: delivery timeline, RACI, status reports, risk management
Ananya Rao — BA: BRD, requirements, gap analysis, process mapping
Imran Sethi — Functional: Odoo configuration, all module setup, training
Reem Haddad — Finance/Compliance: VAT, ZATCA, accounting config, intercompany
Karan Mehta — QA: UAT scripts, testing, sign-off
Layla Mansour — Training: user training, change management, Arabic comms
Zeeshan Iqbal — Senior BA/Architect: solution design, requirements, post-review
Fahad Siddiqui — Full-Stack Dev: Python, APIs, BI, DB, architecture
Talha Rauf — Backend Dev: Python, XML/QWeb, OWL/JS, PostgreSQL
Nida Aslam — QA: testing, documentation
Hassan Javed — Tech Docs: documentation, training materials
BD UAE (team 6): Omar Al-Farsi (lead), Priya Nair, Khalid Rahman, Adnan Qureshi
BD Pakistan (team 7): Hamza Sheikh (lead), Ayesha Khan, Usman Malik, Sana Mushtaq
BD KSA (team 8): Faisal Al-Otaibi (lead), Noura, Yousef, Salma
BD North America (team 9): Tyler Brooks (USA), Lena Carver (Canada)

SKILL → PERSON MAPPING (best fit first):
Odoo config/modules → Imran Sethi, Fahad Siddiqui
Python/backend → Talha Rauf, Fahad, Shafat (architecture)
OWL/JS frontend → Talha Rauf
PostgreSQL/DB → Shafat, Talha
DevOps/Linux/deploy → Shafat
AI/LLM integration → Shafat, Muhammad Umer
VAT/ZATCA/Finance → Reem Haddad
BRD/Requirements → Ananya Rao, Zeeshan
UAT/Testing → Karan Mehta, Nida
Training → Layla Mansour
Project management → Kamran Ali
Client communication → Bilal
Arabic content → Reem, Layla, Salma, Faisal
Tech documentation → Hassan Javed

PIPELINE ROUTING:
UAE lead → Omar → [qualified] → Bilal → discovery → Ananya BRD → proposal → Kamran delivery
KSA lead → Faisal → [qualified] → Bilal → same flow
Pakistan lead → Hamza → [qualified] → Bilal → same flow
NA lead → Tyler/Lena → [qualified] → Bilal → same flow

KEY CLIENTS: Gulf Closets (UAE), RIS CO (KSA), Trace Trading (UAE), BRB Group (Pakistan), edenrobe, Nestle Pakistan, GroupM
ACTIVE PROPOSAL: RVOS KSA — USD 14,000 (invoice verification USD 12K + IMPA cataloguing USD 2K), contact Rizwan Nizami

AGENT RULES:
- Never use AI/automation language in client documents
- UAE entity cannot issue KSA tax invoices directly
- Standard-first Odoo: 95% config, minimal custom code
- Outbound email: separate sending domain, not core2plus.com
- Credentials: vault reference only, never store in Odoo
"""

class C2PMasterAgent(models.TransientModel):
    _name = "c2p.master.agent"
    _description = "C2P Master Agent"
    command = fields.Text(string="Command")
    conversation = fields.Text(string="Conversation", readonly=True, default="")
    thinking = fields.Boolean(string="Thinking", default=False)

    def _get_system_context(self):
        env = self.env
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        # Team + skills + workload
        employees = env["hr.employee"].search_read([("active","=",True)],["name","job_title","department_id","user_id"],limit=60)
        skills_data = {}
        for emp in employees:
            sx = env["hr.employee.skill"].search_read([("employee_id","=",emp["id"])],["skill_id","skill_level_id","skill_type_id"])
            skills_data[emp["name"]] = [f"{s['skill_id'][1]} [{s['skill_level_id'][1]}]" for s in sx if s.get("skill_id") and s.get("skill_level_id")]
        workload = {}
        for t in env["project.task"].search_read([("stage_id.fold","=",False),("active","=",True)],["user_ids"]):
            for uid in (t.get("user_ids") or []):
                workload[uid] = workload.get(uid,0)+1
        team_data = []
        for e in employees:
            uid_val = e["user_id"][0] if e.get("user_id") else None
            team_data.append({"name":e["name"],"title":e.get("job_title",""),"dept":e["department_id"][1] if e.get("department_id") else "","skills":skills_data.get(e["name"],[])[:5],"open_tasks":workload.get(uid_val,0),"availability":"HIGH" if workload.get(uid_val,0)<3 else "MEDIUM" if workload.get(uid_val,0)<7 else "LOW — OVERLOADED"})

        # Projects
        projects = env["project.project"].search_read([("active","=",True)],["name","partner_id","date","task_count"])
        project_detail = []
        for p in projects:
            ptasks = env["project.task"].search_read([("project_id","=",p["id"]),("active","=",True),("stage_id.fold","=",False)],["name","user_ids","date_deadline","priority","stage_id"])
            overdue = [t for t in ptasks if t.get("date_deadline") and str(t["date_deadline"])<today]
            unassigned = [t for t in ptasks if not t.get("user_ids")]
            project_detail.append({"name":p["name"],"client":p["partner_id"][1] if p.get("partner_id") else "Internal","deadline":str(p.get("date","")) or "None","total_tasks":len(ptasks),"overdue":len(overdue),"unassigned":len(unassigned),"health":"RED" if len(overdue)>2 else "AMBER" if len(overdue)>0 or len(unassigned)>3 else "GREEN","tasks":[{"name":t["name"],"stage":t["stage_id"][1] if t.get("stage_id") else "","assigned":[],"deadline":str(t.get("date_deadline","")),"priority":"HIGH" if t.get("priority")=="1" else "normal","overdue":str(t.get("date_deadline",""))<today if t.get("date_deadline") else False} for t in ptasks[:12]]})

        # CRM
        leads = env["crm.lead"].search_read([("active","=",True),("type","=","opportunity")],["name","partner_name","stage_id","team_id","user_id","expected_revenue","probability","write_date"],limit=300)
        by_stage={}; by_team={}; stalled=[]; high_val=[]
        for l in leads:
            st=l["stage_id"][1] if l.get("stage_id") else "Unknown"
            tm=l["team_id"][1] if l.get("team_id") else "Unassigned"
            rev=l.get("expected_revenue",0) or 0
            by_stage[st]=by_stage.get(st,{"count":0,"value_aed":0}); by_stage[st]["count"]+=1; by_stage[st]["value_aed"]+=rev
            by_team[tm]=by_team.get(tm,{"count":0,"value_aed":0}); by_team[tm]["count"]+=1; by_team[tm]["value_aed"]+=rev
            if l.get("write_date") and str(l["write_date"])[:10]<week_ago:
                stalled.append({"company":(l.get("partner_name") or l["name"])[:40],"stage":st,"team":tm,"days_stale":(now-datetime.fromisoformat(str(l["write_date"])[:19])).days})
            if rev>50000:
                high_val.append({"company":(l.get("partner_name") or l["name"])[:40],"stage":st,"value_aed":rev,"probability":l.get("probability",0),"owner":l["user_id"][1] if l.get("user_id") else "Unassigned"})
        total_val=sum(l.get("expected_revenue",0) or 0 for l in leads)
        new_week=env["crm.lead"].search_count([("active","=",True),("create_date",">=",week_ago)])

        # Finance
        finance={}
        try:
            inv=env["account.move"].search_read([("move_type","in",["out_invoice"]),("state","=","posted"),("payment_state","!=","paid")],["partner_id","amount_residual","invoice_date_due"],limit=50)
            ov=[i for i in inv if i.get("invoice_date_due") and str(i["invoice_date_due"])<today]
            finance={"open_count":len(inv),"open_aed":round(sum(i.get("amount_residual",0) or 0 for i in inv),2),"overdue_count":len(ov),"overdue_aed":round(sum(i.get("amount_residual",0) or 0 for i in ov),2),"chase_list":[{"client":i["partner_id"][1] if i.get("partner_id") else "?","amount_aed":round(i.get("amount_residual",0),2),"due":str(i.get("invoice_date_due",""))} for i in sorted(ov,key=lambda x:x.get("amount_residual",0),reverse=True)[:5]]}
        except Exception:
            finance={"note":"unavailable"}

        # Alerts
        alerts=[]
        if finance.get("overdue_count",0)>0: alerts.append(f"🔴 URGENT: {finance['overdue_count']} overdue invoices AED {finance.get('overdue_aed',0):,.0f}")
        for pd in project_detail:
            if pd["overdue"]>0: alerts.append(f"🔴 Project '{pd['name']}': {pd['overdue']} overdue tasks")
            if pd["unassigned"]>3: alerts.append(f"🟡 Project '{pd['name']}': {pd['unassigned']} unassigned tasks")
        for m in [m for m in team_data if m["open_tasks"]>8]: alerts.append(f"🟡 {m['name']} overloaded: {m['open_tasks']} open tasks")
        if stalled: alerts.append(f"🟡 {len(stalled)} pipeline leads stalled 7+ days")
        if not alerts: alerts.append("✅ No critical alerts")

        return {"snapshot":now.strftime("%Y-%m-%d %H:%M"),"team":team_data,"projects":project_detail,"crm":{"total":len(leads),"total_pipeline_aed":round(total_val,2),"new_this_week":new_week,"by_stage":by_stage,"by_team":by_team,"stalled_top10":sorted(stalled,key=lambda x:x["days_stale"],reverse=True)[:10],"high_value":sorted(high_val,key=lambda x:x["value_aed"],reverse=True)[:10]},"finance":finance,"alerts":alerts}

    def _build_prompt(self,cmd,ctx):
        return (
            "You are the C2P Master Agent — AI business operator embedded in Odoo ERP.\n\n"
            "=== COMPANY KNOWLEDGE BASE ===\n"
            + C2P_KNOWLEDGE +
            "\n=== LIVE ODOO DATA ===\n"
            + json.dumps(ctx,indent=2,default=str) +
            "\n\n=== OPERATING RULES ===\n"
            "- Be direct. No filler. No 'Great question!'\n"
            "- When assigning tasks: match skill + pick person with lowest open_tasks + HIGH availability\n"
            "- Priority: revenue risk > delivery risk > efficiency\n"
            "- Always explain WHY you chose a person or action\n"
            "- Flag risks proactively even if not asked\n"
            "- AED for UAE financials, PKR for Pakistan, USD for international\n"
            "- Never suggest AI/automation language for client documents\n\n"
            "=== AVAILABLE ACTIONS ===\n"
            "Append at end of response if acting:\n"
            "```action\n{\"type\":\"assign_task\",\"task_name\":\"...\",\"user\":\"...\"}\n```\n"
            "```action\n{\"type\":\"create_task\",\"project\":\"...\",\"task_name\":\"...\",\"user\":\"...\"}\n```\n\n"
            "=== USER COMMAND ===\n" + cmd
        )

    def _call_ollama(self,prompt):
        url=self.env["ir.config_parameter"].sudo().get_param("c2p.ollama_url","http://127.0.0.1:11434")  # sudo: REVIEW-05 imported from the server as found; reason not yet recorded
        model=self.env["ir.config_parameter"].sudo().get_param("c2p.ollama_model","mistral")  # sudo: REVIEW-05 imported from the server as found; reason not yet recorded
        body=json.dumps({"model":model,"prompt":prompt,"stream":False,"options":{"temperature":0.2,"num_predict":400,"num_ctx":2048}}).encode()
        req=urllib.request.Request(f"{url}/api/generate",data=body,headers={"content-type":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=180) as r: return json.loads(r.read().decode()).get("response","No response.")  # nosec B310 - REVIEW-05: URL scheme not validated, open item
        except Exception as e: raise UserError(f"Ollama error: {str(e)[:150]}\nRun: systemctl start ollama")

    def _call_claude(self,prompt):
        ak=self.env["ir.config_parameter"].sudo().get_param("c2p.anthropic_key","")  # sudo: REVIEW-05 imported from the server as found; reason not yet recorded
        if not ak: raise UserError("No LLM. Start Ollama (systemctl start ollama) or set c2p.anthropic_key.")
        body=json.dumps({"model":"claude-sonnet-4-6","max_tokens":2000,"messages":[{"role":"user","content":prompt}]}).encode()
        req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,headers={"x-api-key":ak,"anthropic-version":"2023-06-01","content-type":"application/json"})
        with urllib.request.urlopen(req,timeout=60) as r: return json.loads(r.read().decode()).get("content",[{}])[0].get("text","")  # nosec B310 - REVIEW-05: URL scheme not validated, open item

    def _execute_actions(self,text):
        import re
        result=text
        for m in re.finditer(r'```action\s*(.*?)\s*```',text,re.S):
            try:
                act=json.loads(m.group(1)); atype=act.get("type","")
                if atype=="assign_task":
                    task=self.env["project.task"].search([("name","ilike",act.get("task_name",""))],limit=1)
                    user=self.env["res.users"].search([("name","ilike",act.get("user",""))],limit=1)
                    if task and user: task.user_ids=[(4,user.id)]; result=result.replace(m.group(0),f"\n✅ Assigned '{task.name}' to {user.name}")
                    else: result=result.replace(m.group(0),f"\n⚠️ Not found: task='{act.get('task_name')}' user='{act.get('user')}'")
                elif atype=="create_task":
                    proj=self.env["project.project"].search([("name","ilike",act.get("project",""))],limit=1)
                    user=self.env["res.users"].search([("name","ilike",act.get("user",""))],limit=1)
                    if proj:
                        vals={"name":act.get("task_name","Task"),"project_id":proj.id}
                        if user: vals["user_ids"]=[(4,user.id)]
                        t=self.env["project.task"].create(vals)
                        result=result.replace(m.group(0),f"\n✅ Created '{t.name}' in {proj.name}"+(f", assigned to {user.name}" if user else ""))
            except Exception as ex: _logger.warning(f"Action error: {ex}"); result=result.replace(m.group(0),"")
        return __import__('re').sub(r'```action.*?```',"",result,flags=__import__('re').S).strip()

    def action_send(self):
        self.ensure_one()
        cmd=(self.command or "").strip()
        if not cmd: raise UserError("Please type a command.")
        ctx=self._get_system_context()
        prompt=self._build_prompt(cmd,ctx)
        try: response=self._call_ollama(prompt)
        except UserError: response=self._call_claude(prompt)
        response=self._execute_actions(response)
        now=datetime.now().strftime("%H:%M")
        prev=self.conversation or ""
        self.write({"conversation":prev+"\n\n"+"─"*40+f"\n[{now}] YOU: {cmd}\n\nAGENT: {response}","command":""})
        return self._reopen()

    def action_clear(self):
        self.write({"conversation":"","command":""}); return self._reopen()

    def action_briefing(self):
        self.command="Morning briefing: 1) All alerts (overdue invoices, overdue tasks, stalled leads) 2) Pipeline by team with AED values 3) Team availability — who is overloaded vs free 4) Top 3 actions TODAY by revenue/delivery impact. Numbers only. Be sharp."
        return self.action_send()

    def action_assign_all(self):
        self.command="Assign all unassigned project tasks. For each task match the best person using: 1) skill fit from knowledge base 2) lowest open_tasks (HIGH availability) 3) department fit. Execute all assignments in Odoo. Summarise each decision."
        return self.action_send()

    def action_pipeline_review(self):
        self.command="Full pipeline review: 1) Counts and AED by stage 2) By team — who has strong vs weak pipeline 3) Stalled leads 7+ days — name, stage, days stale, recommended next action 4) High-value leads >AED 50K — status and what to do NOW. Flag any risks."
        return self.action_send()

    def action_finance_review(self):
        self.command="Finance snapshot: 1) Total open receivables 2) Total overdue with amount 3) Top 5 overdue clients — name, amount, days overdue 4) Who should we chase TODAY and what to say. Flag any red flags."
        return self.action_send()

    def _reopen(self):
        return {"type":"ir.actions.act_window","res_model":"c2p.master.agent","res_id":self.id,"view_mode":"form","target":"new"}
