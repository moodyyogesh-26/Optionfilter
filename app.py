col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Calls (CE) ({len(calls_df)})")
        st.dataframe(
            calls_df[display_cols].style
            .map(color_change, subset=['change %'])
            .format(format_dict)
            .set_properties(**{'font-weight': '600', 'text-align': 'center', 'font-size': '16px'}),
            hide_index=True,
            column_order=default_visible_cols,
            use_container_width=True,
            height=1800
        )
        # ADD YOUR CUSTOM DOWNLOAD BUTTON FOR CALLS HERE:
        csv_calls = calls_df[display_cols].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Calls Data",
            data=csv_calls,
            file_name=f"JSTT_Calls_{get_ist_now().strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )

    with col2:
        st.subheader(f"Puts (PE) ({len(puts_df)})")
        st.dataframe(
            puts_df[display_cols].style
            .map(color_change, subset=['change %'])
            .format(format_dict)
            .set_properties(**{'font-weight': '600', 'text-align': 'center', 'font-size': '16px'}),
            hide_index=True,
            column_order=default_visible_cols, 
            use_container_width=True,
            height=1800
        )
        # ADD YOUR CUSTOM DOWNLOAD BUTTON FOR PUTS HERE:
        csv_puts = puts_df[display_cols].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Puts Data",
            data=csv_puts,
            file_name=f"JSTT_Puts_{get_ist_now().strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )
