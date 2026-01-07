# --- 6. TELAS ---
    if sel == "Investimentos":
        st.markdown("### 📊 Performance e ROI por Obra")
        
        if not df_obras.empty:
            # --- NOVO: SELEÇÃO POR BOTÕES (PÍLULAS) ---
            st.write("Selecione o Empreendimento:")
            lista_obras = df_obras['Cliente'].tolist()
            
            # O option_menu dentro do conteúdo cria botões clicáveis horizontais
            escolha = option_menu(
                menu_title=None,
                options=lista_obras,
                icons=["house"] * len(lista_obras),
                menu_icon="cast",
                default_index=0,
                orientation="horizontal",
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent"},
                    "nav-link": {
                        "font-size": "13px", 
                        "text-align": "center", 
                        "margin": "5px", 
                        "background-color": "#FFFFFF", 
                        "border": "1px solid #E9ECEF",
                        "color": "#495057"
                    },
                    "nav-link-selected": {"background-color": "#2D6A4F", "color": "#FFFFFF"},
                }
            )
            
            st.markdown("---")
            
            # Filtro Seguro baseado na escolha dos botões
            dados_obra = df_obras[df_obras['Cliente'] == escolha].iloc[0]
            vgv = dados_obra['Valor Total']
            
            fin_obra = df_fin[df_fin['Obra Vinculada'] == escolha] if not df_fin.empty else pd.DataFrame()
            
            # Cálculos com proteção
            custos = fin_obra[fin_obra['Tipo'].str.contains('Saída', na=False)]['Valor'].sum() if not fin_obra.empty else 0
            lucro = vgv - custos
            roi = (lucro / custos * 100) if custos > 0 else 0
            
            # Cards de Métricas
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("VGV (Venda)", f"R$ {vgv:,.2f}")
            c2.metric("Custo Total", f"R$ {custos:,.2f}", delta=f"{(custos/vgv*100 if vgv>0 else 0):.1f}% do VGV", delta_color="inverse")
            c3.metric("Lucro Estimado", f"R$ {lucro:,.2f}")
            c4.metric("ROI Atual", f"{roi:.1f}%")

            st.markdown("<br>", unsafe_allow_html=True)
            
            # Gráfico de Evolução
            if not fin_obra.empty and custos > 0:
                df_ev = fin_obra[fin_obra['Tipo'].str.contains('Saída')].sort_values('Data_DT')
                fig = px.line(df_ev, x='Data_DT', y='Valor', title=f"Histórico de Custos: {escolha}", markers=True, color_discrete_sequence=['#2D6A4F'])
                fig.update_layout(xaxis_tickformat='%d/%m/%Y', plot_bgcolor='white', xaxis_title="Data")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"ℹ️ {escolha}: Nenhum gasto registrado ainda.")
        else:
            st.warning("⚠️ Nenhuma obra cadastrada para exibição.")
