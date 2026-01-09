            for future in as_completed(future_to_cluster):
                results.append(future.result())

        # 3.3 Save Results (Main Thread)
        for res in results:
            cluster_id = res["cluster_id"]
            db_cluster = cluster_map.get(cluster_id)
            
            if "error" in res:
                # Handle error case
                db_cluster.ai_summary = f"Analysis Failed: {res['error']}"
                db_cluster.severity = "Low"
                db.commit()
                continue

            analysis_result = res["result"]
            
            # Handle both dict (new) and str (legacy/fallback)
            if isinstance(analysis_result, dict):
                root_cause = analysis_result.get("root_cause", "Unknown")
                if isinstance(root_cause, list):
                    root_cause = "\n".join(str(item) for item in root_cause)
                    
                solution = analysis_result.get("solution", "No solution provided")
                if isinstance(solution, list):
                    solution = "\n".join(str(item) for item in solution)
                    
                ai_summary = analysis_result.get("ai_summary", "Analysis pending...")
                severity = analysis_result.get("severity", "Medium")
                category = analysis_result.get("category", "Uncategorized")
                confidence_score = analysis_result.get("confidence_score", 0)
                suggested_assignment = analysis_result.get("suggested_assignment", "Unknown")
            else:
                # Fallback for string response
                root_cause = "See summary"
                solution = "See summary"
                ai_summary = str(analysis_result)
                severity = "Medium"
                category = "Uncategorized"
                confidence_score = 0
                suggested_assignment = "Unknown"
            
            # Update cluster with analysis
            db_cluster.common_root_cause = root_cause
            db_cluster.common_solution = solution
            db_cluster.ai_summary = ai_summary
            db_cluster.severity = severity
            db_cluster.category = category
            db_cluster.confidence_score = confidence_score
            db_cluster.suggested_assignment = suggested_assignment
            db.commit()
            
            # Link all failures in this cluster to the analysis
            for failure in res["failures"]:
                # Check if analysis already exists
                existing_analysis = db.query(models.FailureAnalysis).filter(models.FailureAnalysis.test_case_id == failure.id).first()
                
                if existing_analysis:
                    existing_analysis.cluster_id = db_cluster.id
                    existing_analysis.root_cause = root_cause
                    existing_analysis.suggested_solution = solution
                else:
                    analysis_record = models.FailureAnalysis(
                        test_case_id=failure.id,
                        cluster_id=db_cluster.id,
                        root_cause=root_cause,
                        suggested_solution=solution
                    )
                    db.add(analysis_record)
                db.commit()
        
        # Mark analysis as completed
        if run:
            run.analysis_status = "completed"
            db.commit()
            
    except Exception as e:
        print(f"Analysis failed: {e}")
        if run:
            run.analysis_status = "failed"
            db.commit()

@router.post("/run/{run_id}")
async def trigger_analysis(run_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Check if run exists
    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    # Set analysis status to 'analyzing'
    run.analysis_status = "analyzing"
    db.commit()
    
    # Run analysis in background
    background_tasks.add_task(run_analysis_task, run_id, db)
    
    return {"message": "Analysis started in background"}

@router.get("/run/{run_id}/status")
def get_analysis_status(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.TestRun).filter(models.TestRun.id == run_id).first()
