def fill_indicator():
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Preencher Indicador")

    # Carregar indicadores
    indicators = load_indicators()

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Filtrar indicadores pelo setor do usuário (se for operador)
    user_type = st.session_state.user_type
    user_sector = st.session_state.user_sector
    # Nome do usuário para registro em log
    user_name = st.session_state.get("user_name", "Usuário não identificado")

    if user_type == "Operador":
        indicators = [ind for ind in indicators if ind["responsavel"] == user_sector]
        if not indicators:
            st.info(f"Não há indicadores associados ao seu setor ({user_sector}).")
            st.markdown('</div>', unsafe_allow_html=True)
            return

    # Selecionar indicador para preencher
    indicator_names = [ind["nome"] for ind in indicators]
    selected_indicator_name = st.selectbox("Selecione um indicador para preencher:", indicator_names)
    selected_indicator = next((ind for ind in indicators if ind["nome"] == selected_indicator_name), None)

    if selected_indicator:
        st.subheader(f"Informações do Indicador: {selected_indicator['nome']}")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Objetivo:** {selected_indicator['objetivo']}")
            st.markdown(f"**Fórmula de Cálculo:** {selected_indicator['calculo']}")
        with col2:
            st.markdown(f"**Meta:** {selected_indicator['meta']}")
            st.markdown(f"**Comparação:** {selected_indicator['comparacao']}")
            st.markdown(f"**Setor Responsável:** {selected_indicator['responsavel']}")
        st.markdown("---")
        st.subheader("Adicionar Novo Resultado")
        with st.form("adicionar_resultado"):
            col1, col2 = st.columns(2)
            with col1:
                mes = st.selectbox("Mês",
                                   options=range(1, 13),
                                   format_func=lambda x: datetime(2023, x, 1).strftime("%B"))
            with col2:
                ano = st.selectbox("Ano",
                                   options=range(datetime.now().year - 5, datetime.now().year + 1),
                                   index=5)
            resultado = st.number_input("Resultado", step=0.01)
            observacoes = st.text_area("Observações (opcional)",
                                       placeholder="Adicione informações relevantes sobre este resultado")
            # Análise Crítica 5W2H
            st.markdown("### Análise Crítica (5W2H)")
            st.markdown("""
            <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                <p style="margin: 0; font-size: 14px;">
                    A metodologia 5W2H ajuda a estruturar a análise crítica de forma completa, 
                    abordando todos os aspectos relevantes da situação.
                </p>
            </div>
            """, unsafe_allow_html=True)
            what = st.text_area("O que (What)",
                                placeholder="O que está acontecendo? Qual é a situação atual do indicador?")
            why = st.text_area("Por que (Why)",
                               placeholder="Por que isso está acontecendo? Quais são as causas?")
            who = st.text_area("Quem (Who)",
                               placeholder="Quem é responsável? Quem está envolvido?")
            when = st.text_area("Quando (When)",
                                placeholder="Quando isso aconteceu? Qual é o prazo para resolução?")
            where = st.text_area("Onde (Where)",
                                 placeholder="Onde ocorre a situação? Em qual processo ou área?")
            how = st.text_area("Como (How)",
                               placeholder="Como resolver a situação? Quais ações devem ser tomadas?")
            howMuch = st.text_area("Quanto custa (How Much)",
                                   placeholder="Quanto custará implementar a solução? Quais recursos são necessários?")
            submitted = st.form_submit_button("Salvar Resultado")

        if submitted:
            if resultado is not None:
                data_referencia = datetime(ano, mes, 1).isoformat()
                analise_critica = {
                    "what": what, "why": why, "who": who, "when": when,
                    "where": where, "how": how, "howMuch": howMuch
                }
                analise_critica_json = json.dumps(analise_critica)
                results = load_results()
                existing_result = next(
                    (r for r in results
                     if r["indicator_id"] == selected_indicator["id"] and r["data_referencia"] == data_referencia), None)

                if existing_result:
                    overwrite = st.checkbox("Já existe um resultado para este período. Deseja sobrescrever?")
                    if overwrite:
                        for r in results:
                            if r["indicator_id"] == selected_indicator["id"] and r["data_referencia"] == data_referencia:
                                r["resultado"] = resultado
                                r["observacao"] = observacoes
                                r["analise_critica"] = analise_critica_json
                                r["data_atualizacao"] = datetime.now().isoformat()
                                r["usuario"] = user_name  # REGISTRO
                        save_results(results)
                        st.success(f"Resultado atualizado com sucesso para {datetime(ano, mes, 1).strftime('%B/%Y')}!")
                else:
                    new_result = {
                        "indicator_id": selected_indicator["id"],
                        "data_referencia": data_referencia,
                        "resultado": resultado,
                        "observacao": observacoes,
                        "analise_critica": analise_critica_json,
                        "data_criacao": datetime.now().isoformat(),
                        "data_atualizacao": datetime.now().isoformat(),
                        "usuario": user_name  # REGISTRO
                    }
                    results.append(new_result)
                    save_results(results)
                    st.success(f"Resultado adicionado com sucesso para {datetime(ano, mes, 1).strftime('%B/%Y')}!")
            else:
                st.warning("Por favor, informe o resultado.")

        # Exibir resultados anteriores
        st.subheader("Resultados Anteriores")
        results = load_results()
        indicator_results = [r for r in results if r["indicator_id"] == selected_indicator["id"]]

        if indicator_results:
            df_results = pd.DataFrame(indicator_results)
            df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"])
            df_results = df_results.sort_values("data_referencia", ascending=False)
            df_display = df_results.copy()
            df_display["Período"] = df_display["data_referencia"].apply(lambda x: x.strftime("%B/%Y"))
            df_display["Resultado"] = df_display["resultado"]
            if "observacao" in df_display.columns:
                df_display["Observações"] = df_display["observacao"]
            else:
                df_display["Observações"] = ""
            if "data_atualizacao" in df_display.columns:
                df_display["Data de Atualização"] = pd.to_datetime(df_display["data_atualizacao"]).dt.strftime(
                    "%d/%m/%Y %H:%M")
            else:
                df_display["Data de Atualização"] = "N/A"
            if "analise_critica" in df_display.columns:
                df_display["Análise Crítica"] = df_display["analise_critica"].apply(
                    lambda x: "✅ Preenchida" if x and x.strip() != "{}" else "❌ Não preenchida"
                )
            else:
                df_display["Análise Crítica"] = "❌ Não preenchida"
            df_display = df_display[["Período", "Resultado", "Observações", "Análise Crítica", "Data de Atualização"]]
            st.dataframe(df_display, use_container_width=True)

            st.subheader("Visualizar/Editar Análise Crítica")
            periodos = df_results["data_referencia"].dt.strftime("%B/%Y").tolist()
            selected_periodo = st.selectbox("Selecione um período:", periodos)
            selected_result_index = df_results[df_results["data_referencia"].dt.strftime("%B/%Y") == selected_periodo].index[0]
            selected_result = df_results.loc[selected_result_index]
            has_analise = False
            analise_dict = {"what": "", "why": "", "who": "", "when": "", "where": "", "how": "", "howMuch": ""}
            if "analise_critica" in selected_result and selected_result["analise_critica"]:
                try:
                    analise_dict = json.loads(selected_result["analise_critica"])
                    has_analise = True
                except:
                    pass
            with st.expander("Análise Crítica 5W2H", expanded=True):
                if has_analise:
                    st.info(f"Visualizando análise crítica para o período {selected_periodo}")
                else:
                    st.warning(f"Não há análise crítica para o período {selected_periodo}. Preencha abaixo.")

                with st.form("editar_analise"):
                    what_edit = st.text_area("O que (What)", value=analise_dict.get("what", ""))
                    why_edit = st.text_area("Por que (Why)", value=analise_dict.get("why", ""))
                    who_edit = st.text_area("Quem (Who)", value=analise_dict.get("who", ""))
                    when_edit = st.text_area("Quando (When)", value=analise_dict.get("when", ""))
                    where_edit = st.text_area("Onde (Where)", value=analise_dict.get("where", ""))
                    how_edit = st.text_area("Como (How)", value=analise_dict.get("how", ""))
                    howMuch_edit = st.text_area("Quanto custa (How Much)", value=analise_dict.get("howMuch", ""))
                    submit_edit = st.form_submit_button("Atualizar Análise Crítica")
                if submit_edit:
                    nova_analise = {
                        "what": what_edit,
                        "why": why_edit,
                        "who": who_edit,
                        "when": when_edit,
                        "where": where_edit,
                        "how": how_edit,
                        "howMuch": howMuch_edit
                    }
                    nova_analise_json = json.dumps(nova_analise)
                    df_results.at[selected_result_index, "analise_critica"] = nova_analise_json
                    if "data_atualizacao" in df_results.columns:
                        df_results.at[selected_result_index, "data_atualizacao"] = datetime.now().isoformat()
                    for i, r in enumerate(results):
                        if r["indicator_id"] == selected_indicator["id"] and r["data_referencia"] == selected_result[
                            "data_referencia"]:
                            results[i]["analise_critica"] = nova_analise_json
                            # Atualização do log do usuário
                            if "data_atualizacao" in results[i]:
                                results[i]["data_atualizacao"] = datetime.now().isoformat()
                            else:
                                results[i]["data_atualizacao"] = datetime.now().isoformat()
                            if "usuario" not in results[i]:
                                results[i]["usuario"] = user_name
                    save_results(results)
                    st.success(f"Análise crítica atualizada com sucesso para {selected_periodo}!")
                    st.rerun()

            st.subheader("Gráfico de Evolução")
            fig = create_chart(selected_indicator["id"], selected_indicator["tipo_grafico"])
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Não foi possível gerar o gráfico.")
            if st.button("📥 Exportar Resultados para Excel"):
                export_df = df_display.copy()
                download_link = get_download_link(export_df,
                                                  f"resultados_{selected_indicator['nome'].replace(' ', '_')}.xlsx",
                                                  "📥 Clique aqui para baixar os dados em Excel")
                st.markdown(download_link, unsafe_allow_html=True)
        else:
            st.info("Nenhum resultado registrado para este indicador.")

        # --------------- LOG DE PREENCHIMENTO (NOVO BLOCO) ---------------
        st.markdown("---")
        # Carregar todos os resultados após possíveis atualizações
        all_results = load_results()
        log_results = [r for r in all_results if r["indicator_id"] == selected_indicator["id"]]
        log_results = sorted(log_results, key=lambda x: x.get("data_atualizacao", ""), reverse=True)
        if log_results:
            log_df = pd.DataFrame(log_results)
            log_df["Data do Preenchimento"] = log_df.get("data_atualizacao", log_df.get("data_criacao", datetime.now().isoformat()))

            # Verificar se é um Timestamp antes de formatar
            log_df["Data do Preenchimento"] = log_df["Data do Preenchimento"].apply(
                lambda x: x.strftime("%d/%m/%Y %H:%M") if isinstance(x, pd.Timestamp) else str(x)
            )
            log_df["Valor Preenchido"] = log_df["resultado"]
            if "usuario" in log_df.columns:
                log_df["Usuário"] = log_df["usuario"]
            else:
                log_df["Usuário"] = user_name
            log_df["Período"] = pd.to_datetime(log_df["data_referencia"]).dt.strftime("%B/%Y")
            exibir_log = log_df[["Período", "Valor Preenchido", "Usuário", "Data do Preenchimento"]]
            exibir_log = exibir_log.drop_duplicates(subset=["Período", "Valor Preenchido", "Usuário"], keep='first')
        else:
            exibir_log = pd.DataFrame(
                columns=["Período", "Valor Preenchido", "Usuário", "Data do Preenchimento"]
            )
        with st.expander("📜 Log de Preenchimentos (clique para visualizar)", expanded=False):
            if exibir_log.empty:
                st.info("Nenhum registro de preenchimento encontrado para este indicador.")
            else:
                st.dataframe(exibir_log, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)
