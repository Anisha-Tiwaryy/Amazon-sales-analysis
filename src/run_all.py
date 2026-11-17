"""Run the whole pipeline: data, cleaning, SQL questions, playbook, tracker, charts, brief."""
import generate_data, clean, run_analysis, playbook, tracker, charts, brief

if __name__ == "__main__":
    generate_data.main()
    clean.main()
    run_analysis.main()
    playbook.main()
    tracker.build()
    charts.charts(); charts.erd()
    print(brief.build().read_text())
