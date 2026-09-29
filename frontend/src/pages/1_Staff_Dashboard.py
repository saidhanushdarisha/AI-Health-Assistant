import streamlit as st
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "frontend" / "src"))

from ui_styles import apply_hospital_theme
from agents.orchestrator.graph import graph

ICON_PATH = ROOT / "frontend" / "src" / "healthcare.png"
st.set_page_config(page_title="Staff Dashboard", page_icon=str(ICON_PATH), layout="wide")
apply_hospital_theme(ICON_PATH, "Staff Dashboard", "Clinical risk intelligence, triage, knowledge and appointment operations")

# Initialize login state if not present
if "staff_logged_in" not in st.session_state:
    st.session_state.staff_logged_in = False

if not st.session_state.staff_logged_in:
    # --- STAFF LOGIN VIEW ---
    st.markdown(f"<h2 style='text-align: center; padding-bottom: 10px; border-bottom: 1px solid #D6D6D9;'><img src='data:image/png;base64,{icon_b64}' style='height: 32px; vertical-align: middle; margin-right: 8px;'>Staff Portal Login</h2>", unsafe_allow_html=True)
    st.write("")
    st.write("")

    col1, col2, col3 = st.columns([1, 3, 1])

    with col2:
        with st.form("login_form", border=True):
            st.markdown("""
                <h3 style='text-align: center; margin-top: 0; margin-bottom: 0px;'>Sign In</h3>
                <p style='text-align: center; color: #555; font-size: 14px; margin-top: 0; margin-bottom: 5px;'>Enter your credentials to access the secure staff dashboard.</p>
                <hr style='margin-top: 0; margin-bottom: 15px; border: 0; border-top: 1px solid #E6E6E6;'>
            """, unsafe_allow_html=True)
            
            username = st.text_input("Username", placeholder="e.g., admin")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            st.write("") # Small spacer
            
            submit_button = st.form_submit_button("Login", use_container_width=True, type="primary")
            
            if submit_button:
                staff_username = os.getenv("STAFF_USERNAME", "admin")
                staff_password = os.getenv("STAFF_PASSWORD", "1234")
                if username == staff_username and password == staff_password:
                    st.session_state.staff_logged_in = True
                    st.success("Login Successful! Loading dashboard...")
                    st.rerun()
                elif not username or not password:
                    st.warning("Please enter both username and password.")
                else:
                    st.error("Invalid Credentials. Please try again.")

else:
    # --- STAFF DASHBOARD VIEW ---
    st.sidebar.header("Staff Dashboard")
    
    page = st.sidebar.radio(
        "Navigation",
        [
            "Dashboard",
            "Readmission Risk",
            "High-Risk Patients",
            "Health Guidelines",
            "Treatment Procedures",
            "Triage",
            "Appointment",
            "Policy Search"
        ]
    )

    # Push the logout button to the bottom of the sidebar
    st.sidebar.write("")
    st.sidebar.write("")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.staff_logged_in = False
        st.rerun()

    # Load and evaluate registries once (cached) for stats and tab views
    import pandas as pd
    from agents.readmission_risk.tools.tools import predict_readmission
    from agents.high_risk_patients.tools.tools import predict_highrisk

    @st.cache_data
    def get_readmission_data():
        df = pd.read_csv("src/agents/readmission_risk/data/patients.csv")
        predictions = []
        confidences = []
        for _, row in df.iterrows():
            res = predict_readmission.invoke({
                "Age": int(row["Age"]),
                "Gender": row["Gender"],
                "Condition": row["Condition"],
                "Procedure": row["Procedure"],
                "Cost": float(row["Cost"]),
                "Length_of_Stay": int(row["Length_of_Stay"]),
                "Outcome": row["Outcome"],
                "Satisfaction": int(row["Satisfaction"])
            })
            predictions.append(res["Readmission"])
            confidences.append(f"{res['Confidence']}%")
        df["Readmission Prediction"] = predictions
        df["Confidence"] = confidences
        return df

    @st.cache_data
    def get_highrisk_data():
        df = pd.read_csv("src/agents/high_risk_patients/data/patients.csv")
        predictions = []
        confidences = []
        for _, row in df.iterrows():
            res = predict_highrisk.invoke({
                "Respiratory_Rate": int(row["Respiratory_Rate"]),
                "Oxygen_Saturation": int(row["Oxygen_Saturation"]),
                "O2_Scale": int(row["O2_Scale"]),
                "Systolic_BP": int(row["Systolic_BP"]),
                "Heart_Rate": int(row["Heart_Rate"]),
                "Temperature": float(row["Temperature"]),
                "Consciousness": row["Consciousness"],
                "On_Oxygen": int(row["On_Oxygen"])
            })
            predictions.append(res["Risk_Level"])
            confidences.append(f"{res['Risk_Score']}%")
        df["Deterioration Risk"] = predictions
        df["Confidence"] = confidences
        return df


    if page == "Dashboard":
        df_readm_stats = get_readmission_data()
        df_highrisk_stats = get_highrisk_data()

        # Calculate statistics dynamically
        unique_names = set(df_readm_stats["Name"].dropna().unique().tolist() + df_highrisk_stats["Name"].dropna().unique().tolist())
        total_patients_count = len(unique_names)

        high_risk_count = len(df_highrisk_stats[df_highrisk_stats["Deterioration Risk"].str.lower() == "high"])
        readmission_count = len(df_readm_stats[df_readm_stats["Readmission Prediction"].str.lower() == "yes"])

        try:
            df_bookings = pd.read_csv("src/agents/appointment/data/appointments_booked.csv")
            appointments_count = len(df_bookings)
        except Exception:
            appointments_count = 0

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.markdown(f"<div style='text-align: center;'><span style='color: #666; font-size: 14px;'>Total Patients</span><br><span style='font-weight: bold; font-size: 32px; color: #111;'>{total_patients_count}</span></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div style='text-align: center;'><span style='color: #666; font-size: 14px;'>High-Risk Patients</span><br><span style='font-weight: bold; font-size: 32px; color: #111;'>{high_risk_count}</span></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div style='text-align: center;'><span style='color: #666; font-size: 14px;'>Readmission Cases</span><br><span style='font-weight: bold; font-size: 32px; color: #111;'>{readmission_count}</span></div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div style='text-align: center;'><span style='color: #666; font-size: 14px;'>Appointments</span><br><span style='font-weight: bold; font-size: 32px; color: #111;'>{appointments_count}</span></div>", unsafe_allow_html=True)

        st.divider()

        st.subheader("AI Assistant")

        if "dashboard_thread_id" not in st.session_state:
            st.session_state.dashboard_thread_id = str(uuid.uuid4())
        if "dashboard_printed_count" not in st.session_state:
            st.session_state.dashboard_printed_count = 0

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = st.chat_input("Ask AI Assistant")

        if prompt:
            st.session_state.messages.append(
                {"role": "user", "content": prompt}
            )

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Thinking..."):
                config = {"configurable": {"thread_id": st.session_state.dashboard_thread_id}}
                result = graph.invoke(
                    {"user_input": prompt, "route": [], "msg": [], "user_role": "staff"},
                    config=config,
                )

                new_messages = result["msg"][st.session_state.dashboard_printed_count:]
                st.session_state.dashboard_printed_count = len(result["msg"])
                response = "\n\n".join(new_messages) if new_messages else "No response received."

            with st.chat_message("assistant"):
                st.markdown(response)

            st.session_state.messages.append(
                {"role": "assistant", "content": response}
            )

    elif page == "Readmission Risk":
        st.header("Readmission Risk Prediction")
        st.caption("Estimate 30-day patient readmission probability using clinical and demographic data.")
        st.divider()

        df = get_readmission_data()

        st.subheader("Patient Readmission Registry")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.divider()

        # Add interactive prediction form
        st.subheader("Predict Custom Patient Risk")
        with st.form("predict_form", border=True):
            col1, col2 = st.columns(2)
            with col1:
                age = st.number_input("Age", min_value=0, max_value=120, value=50)
                gender = st.selectbox("Gender", ["Female", "Male"])
                condition = st.selectbox("Primary Condition", [
                    "Allergic Reaction", "Appendicitis", "Cancer", "Childbirth", "Diabetes",
                    "Fractured Arm", "Fractured Leg", "Heart Attack", "Heart Disease",
                    "Hypertension", "Kidney Stones", "Osteoarthritis", "Prostate Cancer",
                    "Respiratory Infection", "Stroke"
                ])
                procedure = st.selectbox("Procedure Administered", [
                    "Angioplasty", "Antibiotics and Rest", "Appendectomy",
                    "CT Scan and Medication", "Cardiac Catheterization",
                    "Cast and Physical Therapy", "Delivery and Postnatal Care",
                    "Epinephrine Injection", "Insulin Therapy", "Lithotripsy",
                    "Medication and Counseling", "Physical Therapy and Pain Management",
                    "Radiation Therapy", "Surgery and Chemotherapy", "X-Ray and Splint"
                ])
            with col2:
                cost = st.number_input("Admission Cost ($)", min_value=0.0, value=5000.0, step=500.0)
                los = st.number_input("Length of Stay (Days)", min_value=1, max_value=100, value=4)
                outcome = st.selectbox("Discharge Status / Outcome", ["Recovered", "Stable"])
                satisfaction = st.slider("Patient Satisfaction Rating (1-5)", min_value=1, max_value=5, value=4)

            predict_btn = st.form_submit_button("Predict Risk", type="primary")

            if predict_btn:
                res = predict_readmission.invoke({
                    "Age": int(age),
                    "Gender": gender,
                    "Condition": condition,
                    "Procedure": procedure,
                    "Cost": float(cost),
                    "Length_of_Stay": int(los),
                    "Outcome": outcome,
                    "Satisfaction": int(satisfaction)
                })

                st.write("")
                if res["Readmission"] == "Yes":
                    st.error(f"**High Risk of Readmission** (Confidence: {res['Confidence']}%)")
                else:
                    st.success(f"**Low Risk of Readmission** (Confidence: {res['Confidence']}%)")

    elif page == "High-Risk Patients":
        st.header("High-Risk Patients Detection")
        st.caption("Classify patient deterioration risk categories (Low, Medium, High, Normal) using physiological vital signs.")
        st.divider()

        df = get_highrisk_data()

        st.subheader("Patient Deterioration Registry")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.divider()

        # Add interactive prediction form
        st.subheader("Evaluate Custom Patient Deterioration Risk")
        with st.form("highrisk_form", border=True):
            col1, col2 = st.columns(2)
            with col1:
                rr = st.number_input("Respiratory Rate (breaths/min)", min_value=0, max_value=60, value=18)
                o2_sat = st.number_input("Oxygen Saturation (%)", min_value=0, max_value=100, value=96)
                o2_scale = st.selectbox("O2 Scale (1 or 2)", [1, 2], index=0)
                systolic_bp = st.number_input("Systolic Blood Pressure (mmHg)", min_value=0, max_value=300, value=120)
            with col2:
                hr = st.number_input("Heart Rate (bpm)", min_value=0, max_value=250, value=75)
                temp = st.number_input("Temperature (°C)", min_value=30.0, max_value=45.0, value=37.0, step=0.1)
                consciousness = st.selectbox("Consciousness Level (A=Alert, V=Voice, P=Pain, U=Unresponsive, C=Confused)", ["A", "C", "P", "U", "V"])
                on_oxygen = st.selectbox("On Supplemental Oxygen?", ["No (0)", "Yes (1)"])

            predict_btn = st.form_submit_button("Assess Risk", type="primary")

            if predict_btn:
                ox_val = 1 if "Yes" in on_oxygen else 0
                res = predict_highrisk.invoke({
                    "Respiratory_Rate": int(rr),
                    "Oxygen_Saturation": int(o2_sat),
                    "O2_Scale": int(o2_scale),
                    "Systolic_BP": int(systolic_bp),
                    "Heart_Rate": int(hr),
                    "Temperature": float(temp),
                    "Consciousness": consciousness,
                    "On_Oxygen": ox_val
                })

                st.write("")
                risk_lvl = res["Risk_Level"]
                score = res["Risk_Score"]
                
                if risk_lvl == "High":
                    st.error(f"**High Deterioration Risk Detected** (Confidence: {score}%)")
                elif risk_lvl == "Medium":
                    st.warning(f"**Medium Deterioration Risk Detected** (Confidence: {score}%)")
                elif risk_lvl == "Low":
                    st.info(f"**Low Deterioration Risk** (Confidence: {score}%)")
                else:
                    st.success(f"**Normal/Healthy Vital Signs** (Confidence: {score}%)")

    elif page == "Health Guidelines":
        st.header("Health Guidelines")
        st.caption("Ask questions and search standard medical health guidelines.")
        st.divider()

        from agents.orchestrator.router import health_guidelines_db
        from agents.orchestrator.models import router_llm
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        st.subheader("AI Assistant")

        if "guidelines_messages" not in st.session_state:
            st.session_state.guidelines_messages = []

        for msg in st.session_state.guidelines_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = st.chat_input("Ask Health Guidelines Assistant")

        if prompt:
            st.session_state.guidelines_messages.append(
                {"role": "user", "content": prompt}
            )

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Thinking..."):
                if health_guidelines_db is None:
                    response = "The health guidelines database is currently unavailable."
                else:
                    docs = health_guidelines_db.similarity_search(prompt, k=2)
                    context = "\n\n".join([doc.page_content for doc in docs])

                    # Build system message with memory/greeting rules
                    system_instructions = """You are an AI Hospital Assistant specializing in standard medical health guidelines for medical staff.

Rules:
1. Greet the user warmly and handle small talk or general questions politely if the user greets you or asks general capability questions.
2. If the user asks about other services or actions available in the staff portal (like booking appointments, running risk predictions, performing triage, searching procedures, or policy lookup):
- Explain politely that you are the Health Guidelines assistant and cannot perform this task here.
- Direct them to the correct section of the sidebar navigation:
  * Booking/canceling appointments: select "Appointment" in the sidebar navigation.
  * Running triage assessments: select "Triage" in the sidebar navigation.
  * Readmission risk predictions: select "Readmission Risk" in the sidebar navigation.
  * Deterioration risk monitoring: select "High-Risk Patients" in the sidebar navigation.
  * Treatment procedures: select "Treatment Procedures" in the sidebar navigation.
  * Hospital/insurance policy search: select "Policy Search" in the sidebar navigation.
3. If the user asks a medical or health guideline question, explain the guidelines in a friendly, professional, and refined conversational tone, structuring the response clearly (e.g. using formatting or bullet points) so it is easy to read. Stay strictly grounded in the provided DOCUMENT EXCERPTS. Do NOT use your own medical knowledge or invent guidelines not in the excerpts.
4. If the answer cannot be found in the document excerpts, reply exactly:
"I couldn't find this information in the hospital documentation."
5. Use the CONVERSATION HISTORY to keep track of context across turns, allowing the user to ask follow-up questions.
"""
                    messages = [SystemMessage(content=system_instructions)]

                    # Append prior chat memory
                    for msg in st.session_state.guidelines_messages[:-1]:
                        if msg["role"] == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        else:
                            messages.append(AIMessage(content=msg["content"]))

                    # Append current user query with RAG context
                    user_content = f"""DOCUMENT EXCERPTS:
{context}

USER QUESTION:
{prompt}
"""
                    messages.append(HumanMessage(content=user_content))

                    # Invoke LLM to refine response
                    response = router_llm.invoke(messages).content.strip()

            with st.chat_message("assistant"):
                st.markdown(response)

            st.session_state.guidelines_messages.append(
                {"role": "assistant", "content": response}
            )

    elif page == "Treatment Procedures":
        st.header("Treatment Procedures")
        st.caption("Ask questions and search hospital treatment procedures and protocols.")
        st.divider()

        from agents.orchestrator.router import treatment_procedures_db
        from agents.orchestrator.models import router_llm
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        st.subheader("AI Assistant")

        if "procedures_messages" not in st.session_state:
            st.session_state.procedures_messages = []

        for msg in st.session_state.procedures_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = st.chat_input("Ask Treatment Procedures Assistant")

        if prompt:
            st.session_state.procedures_messages.append(
                {"role": "user", "content": prompt}
            )

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Thinking..."):
                if treatment_procedures_db is None:
                    response = "The treatment procedures database is currently unavailable."
                else:
                    docs = treatment_procedures_db.similarity_search(prompt, k=2)
                    context = "\n\n".join([doc.page_content for doc in docs])

                    # Build system message with memory/greeting/other services rules
                    system_instructions = """You are an AI Hospital Assistant specializing in standard hospital treatment procedures and protocols for medical staff.

Rules:
1. Greet the user warmly and handle small talk or general questions politely if the user greets you or asks general capability questions.
2. If the user asks about other services or actions available in the staff portal (like booking appointments, running risk predictions, performing triage, guidelines search, or policy lookup):
- Explain politely that you are the Treatment Procedures assistant and cannot perform this task here.
- Direct them to the correct section of the sidebar navigation:
  * Booking/canceling appointments: select "Appointment" in the sidebar navigation.
  * Running triage assessments: select "Triage" in the sidebar navigation.
  * Readmission risk predictions: select "Readmission Risk" in the sidebar navigation.
  * Deterioration risk monitoring: select "High-Risk Patients" in the sidebar navigation.
  * Medical guidelines search: select "Health Guidelines" in the sidebar navigation.
  * Hospital/insurance policy search: select "Policy Search" in the sidebar navigation.
3. If the user asks a treatment procedure or protocol question, explain the steps clearly and concisely (using numbered steps if there is a sequence) in a friendly, professional, and refined conversational tone, structuring the response clearly so it is easy to read. Stay strictly grounded in the provided DOCUMENT EXCERPTS. Do NOT use your own medical knowledge or invent steps not in the excerpts.
4. If the answer cannot be found in the document excerpts, reply exactly:
"I couldn't find this information in the hospital documentation."
5. Use the CONVERSATION HISTORY to keep track of context across turns, allowing the user to ask follow-up questions.
"""
                    messages = [SystemMessage(content=system_instructions)]

                    # Append prior chat memory
                    for msg in st.session_state.procedures_messages[:-1]:
                        if msg["role"] == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        else:
                            messages.append(AIMessage(content=msg["content"]))

                    # Append current user query with RAG context
                    user_content = f"""DOCUMENT EXCERPTS:
{context}

USER QUESTION:
{prompt}
"""
                    messages.append(HumanMessage(content=user_content))

                    # Invoke LLM to refine response
                    response = router_llm.invoke(messages).content.strip()

            with st.chat_message("assistant"):
                st.markdown(response)

            st.session_state.procedures_messages.append(
                {"role": "assistant", "content": response}
            )

    elif page == "Triage":
        st.header("Triage")
        st.caption("Assess patient symptoms and recommend appropriate clinical departments.")
        st.divider()

        from agents.orchestrator.models import router_llm
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        st.subheader("AI Assistant")

        if "triage_messages" not in st.session_state:
            st.session_state.triage_messages = []

        for msg in st.session_state.triage_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = st.chat_input("Describe the patient's symptoms here...")

        if prompt:
            st.session_state.triage_messages.append(
                {"role": "user", "content": prompt}
            )

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Thinking..."):
                system_instructions = """You are an AI Hospital Triage Assistant for medical staff.

Your role is to perform symptom triage, NOT diagnose diseases.

Objectives:
1. Understand the patient's symptoms.
2. Identify emergency warning signs.
3. Recommend the most appropriate hospital department.
4. Explain your reasoning.
5. Recommend safe next steps.
6. Ask only essential follow-up questions if information is missing.

If the user asks about other services or actions available in the staff portal (like booking appointments, running risk predictions, guidelines search, procedures search, or policy lookup):
- Explain politely that you are the Triage assistant and cannot perform this task here.
- Direct them to the correct section of the sidebar navigation:
  * Booking/canceling appointments: select "Appointment" in the sidebar navigation.
  * Medical guidelines search: select "Health Guidelines" in the sidebar navigation.
  * Readmission risk predictions: select "Readmission Risk" in the sidebar navigation.
  * Deterioration risk monitoring: select "High-Risk Patients" in the sidebar navigation.
  * Treatment procedures: select "Treatment Procedures" in the sidebar navigation.
  * Hospital/insurance policy search: select "Policy Search" in the sidebar navigation.

Never:
- Diagnose diseases.
- Prescribe medication.
- Recommend drug dosages.
- Invent information.
- Ignore emergency symptoms.

Use the CONVERSATION HISTORY to keep track of context across turns, allowing the user to ask follow-up questions or provide more details.

Please evaluate:
• Age
• Sex (if relevant)
• Symptoms
• Duration
• Severity
• Pain location
• Existing medical conditions
• Current medications (if mentioned)
• Allergies (if mentioned)
• Associated symptoms
• Vital signs (if available)

Please format your response clearly using headers and bullet points. Use standard headings:
- **Recommended Department**
- **Emergency Status**
- **Reasoning & Action Plan**
- **Follow-up Questions** (if details are missing)
- **Safety Note**: This is a triage assessment only and is not a medical diagnosis.
"""
                messages = [SystemMessage(content=system_instructions)]

                # Append prior chat memory
                for msg in st.session_state.triage_messages[:-1]:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    else:
                        messages.append(AIMessage(content=msg["content"]))

                # Append current user query
                messages.append(HumanMessage(content=prompt))

                # Invoke LLM to perform triage reasoning
                response = router_llm.invoke(messages).content.strip()

            with st.chat_message("assistant"):
                st.markdown(response)

            st.session_state.triage_messages.append(
                {"role": "assistant", "content": response}
            )

    elif page == "Appointment":
        st.header("Appointment")
        st.caption("Manage doctor schedules and book patient consultations.")
        st.divider()

        import pandas as pd
        from datetime import datetime
        from agents.appointment.tools import APPOINTMENT_TOOLS, book_hospital_appointment
        from agents.orchestrator.router import appointment_tools
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

        # Load real clinicians directory from database
        @st.cache_data
        def load_clinicians():
            df = pd.read_csv("src/agents/appointment/data/doctors.csv")
            return df.rename(columns={
                "doctor_name": "Doctor",
                "department": "Specialty",
                "working_days": "Availability",
                "consultation_fee": "Fee ($)"
            })

        doctors_df = load_clinicians()

        # Available Clinicians Directory - Full Width
        st.subheader("Available Clinicians")
        st.dataframe(doctors_df, use_container_width=True, hide_index=True)
        st.divider()

        # 1. Interactive Form for Quick Booking (without st.form to enable dynamic reactive filtering)
        st.subheader("Schedule Appointment")
        with st.container(border=True):
            patient_name_input = st.text_input("Patient Name", placeholder="Enter full name")
            
            df_slots_raw = pd.read_csv("src/agents/appointment/data/slots_availability.csv")
            available_depts = sorted(df_slots_raw[df_slots_raw["status"].str.lower() == "available"]["department"].unique().tolist())
            
            selected_dept = st.selectbox("Department", ["Select Department..."] + available_depts, index=0)
            
            if selected_dept != "Select Department...":
                available_dates = sorted(df_slots_raw[
                    (df_slots_raw["department"].str.lower() == selected_dept.lower()) & 
                    (df_slots_raw["status"].str.lower() == "available")
                ]["date"].unique().tolist())
                selected_date = st.selectbox("Appointment Date", ["Select Date..."] + available_dates, index=0)
            else:
                selected_date = st.selectbox("Appointment Date", ["Please select a department first..."], disabled=True, index=0)

            if selected_dept != "Select Department..." and selected_date not in ["Select Date...", "Please select a department first..."]:
                available_time_slots = sorted(df_slots_raw[
                    (df_slots_raw["department"].str.lower() == selected_dept.lower()) & 
                    (df_slots_raw["date"] == selected_date) & 
                    (df_slots_raw["status"].str.lower() == "available")
                ]["time_slot"].unique().tolist())
                selected_slot = st.selectbox("Time Slot", ["Select Time Slot..."] + available_time_slots, index=0)
            else:
                selected_slot = st.selectbox("Time Slot", ["Please select a date first..."], disabled=True, index=0)
            
            book_btn = st.button("Confirm Booking", type="primary", use_container_width=True)
            if book_btn:
                if not patient_name_input.strip():
                    st.error("Please enter the patient's name.")
                elif selected_dept == "Select Department...":
                    st.error("Please select a department.")
                elif selected_date in ["Select Date...", "Please select a department first..."]:
                    st.error("Please select an appointment date.")
                elif selected_slot in ["Select Time Slot...", "Please select a date first..."]:
                    st.error("Please select an available time slot.")
                else:
                    with st.spinner("Processing booking..."):
                        result = book_hospital_appointment.invoke({
                            "patient_name": patient_name_input.strip(),
                            "department": selected_dept,
                            "time_slot": selected_slot,
                            "date": selected_date
                        })
                        if "SUCCESS" in result:
                            st.success(result)
                            # Force clear cache so dataframes update on next run
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(result)

        st.divider()

        # 2. Chatbot Interface
        st.subheader("AI Assistant")

        if "appointment_messages" not in st.session_state:
            st.session_state.appointment_messages = []

        for msg in st.session_state.appointment_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = st.chat_input("Ask Appointment Assistant (e.g., book, reschedule, cancel or check schedules)")

        if prompt:
            st.session_state.appointment_messages.append(
                {"role": "user", "content": prompt}
            )

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Thinking..."):
                current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
                system_instructions = f"""You are an AI Hospital Appointment Assistant for medical staff.
Current time: {current_time}.

Objectives:
1. Help staff book, cancel, reschedule, or search appointments using the provided tools.
2. ALWAYS use `check_doctor_availability` before confirming a booking.
3. Gather patient name, department, time_slot, and date for booking.

Rules:
1. Greet the user warmly and handle small talk or general questions politely if the user greets you or asks general capability questions.
2. If the user asks about other services or actions available in the staff portal (like running risk predictions, performing triage, guidelines search, procedures search, or policy lookup):
- Explain politely that you are the Appointment assistant and cannot perform this task here.
- Direct them to the correct section of the sidebar navigation:
  * Running triage assessments: select "Triage" in the sidebar navigation.
  * Medical guidelines search: select "Health Guidelines" in the sidebar navigation.
  * Readmission risk predictions: select "Readmission Risk" in the sidebar navigation.
  * Deterioration risk monitoring: select "High-Risk Patients" in the sidebar navigation.
  * Treatment procedures: select "Treatment Procedures" in the sidebar navigation.
  * Hospital/insurance policy search: select "Policy Search" in the sidebar navigation.
3. Use the CONVERSATION HISTORY to keep track of context across turns.
"""
                messages = [SystemMessage(content=system_instructions)]

                # Append prior chat memory
                for msg in st.session_state.appointment_messages[:-1]:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    else:
                        messages.append(AIMessage(content=msg["content"]))

                # Append current user query
                messages.append(HumanMessage(content=prompt))

                # ReAct loop: invoke appointment tool-calling LLM
                response = appointment_tools.invoke(messages)
                messages.append(response)

                while response.tool_calls:
                    for tool_call in response.tool_calls:
                        selected_tool = next((t for t in APPOINTMENT_TOOLS if t.name == tool_call["name"]), None)
                        if selected_tool:
                            try:
                                tool_output = selected_tool.invoke(tool_call["args"])
                            except Exception as e:
                                tool_output = f"Error: {str(e)}"
                        else:
                            tool_output = "Error: Tool not found."
                        messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))

                    response = appointment_tools.invoke(messages)
                    messages.append(response)

                response_text = response.content

            with st.chat_message("assistant"):
                st.markdown(response_text)

            st.session_state.appointment_messages.append(
                {"role": "assistant", "content": response_text}
            )

    elif page == "Policy Search":
        st.header("Policy Search")
        st.caption("Ask questions and search hospital policies, guidelines, and compliance documents.")
        st.divider()

        from agents.orchestrator.router import policy_db
        from agents.policy_search.models import policy_search_llm
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        st.subheader("AI Assistant")

        if "policy_messages" not in st.session_state:
            st.session_state.policy_messages = []

        for msg in st.session_state.policy_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = st.chat_input("Ask Policy Search Assistant")

        if prompt:
            st.session_state.policy_messages.append(
                {"role": "user", "content": prompt}
            )

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Thinking..."):
                if policy_db is None:
                    response = "The hospital policy database is currently unavailable."
                else:
                    docs = policy_db.similarity_search(prompt, k=3)
                    context = "\n\n".join(d.page_content for d in docs)

                    # Build system message with memory/greeting/other services rules
                    system_instructions = """You are an AI Hospital Policy Assistant for medical staff.

Rules:
1. Greet the user warmly and handle small talk or general questions politely if the user greets you or asks general capability questions.
2. If the user asks about other services or actions available in the staff portal (like booking appointments, running risk predictions, performing triage, guidelines search, or procedures search):
- Explain politely that you are the Policy Search assistant and cannot perform this task here.
- Direct them to the correct section of the sidebar navigation:
  * Booking/canceling appointments: select "Appointment" in the sidebar navigation.
  * Running triage assessments: select "Triage" in the sidebar navigation.
  * Readmission risk predictions: select "Readmission Risk" in the sidebar navigation.
  * Deterioration risk monitoring: select "High-Risk Patients" in the sidebar navigation.
  * Medical guidelines search: select "Health Guidelines" in the sidebar navigation.
  * Treatment procedures: select "Treatment Procedures" in the sidebar navigation.
3. If the user asks a policy or compliance question, explain the policy clearly and concisely in a friendly, professional, and refined conversational tone, structuring the response clearly. Stay strictly grounded in the provided DOCUMENT EXCERPTS. Do NOT invent policies or details not in the excerpts.
4. If the answer cannot be found in the document excerpts, reply exactly:
"I could not find this policy."
5. Use the CONVERSATION HISTORY to keep track of context across turns, allowing the user to ask follow-up questions.
"""
                    messages = [SystemMessage(content=system_instructions)]

                    # Append prior chat memory
                    for msg in st.session_state.policy_messages[:-1]:
                        if msg["role"] == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        else:
                            messages.append(AIMessage(content=msg["content"]))

                    # Append current user query with RAG context
                    user_content = f"""DOCUMENT EXCERPTS:
{context}

USER QUESTION:
{prompt}

Answer format:
Policy:
[Name]

Summary:
[Short explanation]

Details:
- [point 1]
- [point 2]

Reference:
Hospital Documents
"""
                    messages.append(HumanMessage(content=user_content))

                    # Invoke LLM to refine response
                    response = policy_search_llm.invoke(messages).content.strip()

            with st.chat_message("assistant"):
                st.markdown(response)

            st.session_state.policy_messages.append(
                {"role": "assistant", "content": response}
            )
