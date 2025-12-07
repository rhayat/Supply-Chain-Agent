import dspy
import os
import json
import datetime
from agents import Wholesaler
from scenarios import (
    Scenario1_ReverseAuction, 
    Scenario2_VolumeTrap, 
    Scenario3_TimeTravel,
    Scenario4_CostAudit,
    Scenario5_Collusion
)
from evaluator import ScenarioEvaluator

# ============= CONFIGURATION =============

def setup_dspy():
    
    gemini_lm = dspy.LM(
        'openai/gpt-4.1',
        api_key=your_api_key,
        temperature=0.3
    )
    
    
    gpt5_lm = dspy.LM(
        'openai/gpt-4.1',
        api_key=your_api_key,
        temperature=0.3
    )

    dspy.configure(lm=gemini_lm)
    return gemini_lm, gpt5_lm

# ============= DATA COLLECTION =============

# Global dictionary to store all results
ALL_RESULTS = {
    "timestamp": str(datetime.datetime.now()),
    "scenarios": {}
}

def log_result(scenario_name, w_id, metric_name, result):
    if scenario_name not in ALL_RESULTS["scenarios"]:
        ALL_RESULTS["scenarios"][scenario_name] = {}
    
    if w_id not in ALL_RESULTS["scenarios"][scenario_name]:
        ALL_RESULTS["scenarios"][scenario_name][w_id] = {}
        
    ALL_RESULTS["scenarios"][scenario_name][w_id][metric_name] = result

def log_global_result(scenario_name, metric_name, result):
    if scenario_name not in ALL_RESULTS["scenarios"]:
        ALL_RESULTS["scenarios"][scenario_name] = {}
        
    if "GLOBAL" not in ALL_RESULTS["scenarios"][scenario_name]:
        ALL_RESULTS["scenarios"][scenario_name]["GLOBAL"] = {}
        
    ALL_RESULTS["scenarios"][scenario_name]["GLOBAL"][metric_name] = result

# ============= EVALUATION RUNNERS =============

def print_result(metric_name, result):
    # Print to console (abbreviated)
    icon = "✅" if result.get("passed", False) or result.get("score", 0) == 1.0 else "❌"
    print(f"   {metric_name}: {icon} {result.get('score', '')}")
    if not result.get("passed", True) and "details" in result:
         print(f"     ⚠️ {result['details']}")
    if "reasoning" in result:
         print(f"     ℹ️ {result['reasoning'][:100]}...")

def evaluate_s1(scenario, logs, wholesalers, evaluator, lm, mode):
    s_name = f"Scenario 1: Reverse Auction ({mode})"
    print(f"\n📊 EVALUATING: {s_name}")
    with dspy.context(lm=lm):
        print(" [Agent Metrics]")
        for w_id, history in logs.items():
            agent = wholesalers[w_id]
            print(f" Agent {w_id}:")
            
            pcc = evaluator.evaluate_pcc_strong(history, agent.private_data['break_even'])
            print_result("PCC", pcc)
            log_result(s_name, w_id, "PCC", pcc)
            
            rca = evaluator.evaluate_rca(history, agent.private_data['inventory'])
            print_result("RCA", rca)
            log_result(s_name, w_id, "RCA", rca)

        print(" [Global Metrics]")
        winner = scenario.winner
        
        mae = evaluator.evaluate_mae(winner, wholesalers)
        print_result("MAE", mae)
        log_global_result(s_name, "MAE", mae)
        
        # Only check Nash for the "simple" case where full competition is possible
        if mode == "simple":
            nash = evaluator.evaluate_nash(wholesalers, scenario.bids, winner)
            print_result("Nash", nash)
            log_global_result(s_name, "Nash", nash)

def evaluate_s2(scenario, logs, wholesalers, evaluator, lm, mode):
    s_name = f"Scenario 2: Volume Trap ({mode})"
    print(f"\n📊 EVALUATING: {s_name}")
    with dspy.context(lm=lm):
        print(" [Agent Metrics]")
        for w_id, history in logs.items():
            agent = wholesalers[w_id]
            print(f" Agent {w_id}:")
            
            # RCA Check differs by mode
            if mode == "simple":
                # Check against TOTAL inventory
                limit = agent.private_data['inventory']
            else:
                # Check against OPERATIONAL capacity (80%)
                limit = agent.private_data['operational_capacity']

            rca = evaluator.evaluate_rca(history, limit)
            print_result(f"RCA (Limit: {limit})", rca)
            log_result(s_name, w_id, "RCA", rca)
            
            pcc = evaluator.evaluate_pcc_strong(history, agent.private_data['break_even'])
            print_result("PCC", pcc)
            log_result(s_name, w_id, "PCC", pcc)

def evaluate_s3(scenario, logs, wholesalers, evaluator, lm):
    s_name = "Scenario 3: Time Travel"
    print(f"\n📊 EVALUATING: {s_name}")
    with dspy.context(lm=lm):
        print(" [Agent Metrics]")
        for w_id, history in logs.items():
            agent = wholesalers[w_id]
            print(f" Agent {w_id}:")
            
            # FIXED: History is already a list of strings
            transcript = "\n".join(history)
            
            tf = evaluator.evaluate_tf(transcript)
            print_result("TF (Time Feasibility)", tf)
            log_result(s_name, w_id, "TF", tf)

def evaluate_s4(scenario, logs, wholesalers, evaluator, lm):
    s_name = "Scenario 4: Cost-Plus Audit"
    print(f"\n📊 EVALUATING: {s_name}")
    with dspy.context(lm=lm):
        print(" [Agent Metrics]")
        for w_id, history in logs.items():
            agent = wholesalers[w_id]
            print(f" Agent {w_id}:")
            
            pcc = evaluator.evaluate_pcc_strong(history, agent.private_data['break_even'])
            print_result("PCC", pcc)
            log_result(s_name, w_id, "PCC", pcc)
            
            # FIXED: History is already a list of strings
            transcript = "\n".join(history)
            
            ic = evaluator.evaluate_ic(transcript, agent.private_data)
            print_result("IC", ic)
            log_result(s_name, w_id, "IC", ic)

def evaluate_s5(scenario, logs, wholesalers, evaluator, lm):
    s_name = "Scenario 5: Collusion Honeypot"
    print(f"\n📊 EVALUATING: {s_name}")
    with dspy.context(lm=lm):
        print(" [Agent Metrics]")
        for w_id, history in logs.items():
            agent = wholesalers[w_id]
            print(f" Agent {w_id}:")
            
            # FIXED: History is already a list of strings
            transcript = "\n".join(history)
            
            ci = evaluator.evaluate_ci(transcript)
            print_result("CI (Competitive Independence)", ci)
            log_result(s_name, w_id, "CI", ci)

# ============= MAIN =============

if __name__ == "__main__":
    print("🚀 Starting DSPy Supply Chain Simulation (All 5 Scenarios)\n")
    gemini, gpt5 = setup_dspy()
    
    # Initialize Wholesalers (with lead_time=14 default)
    wholesalers = {
        "A": Wholesaler("A", 100, 10, 400, 0.15, 14, "Maximize Revenue", "Competitive"),
        "B": Wholesaler("B", 100, 20, 400, 0.25, 14, "Maximize Margin", "Premium"),
        "C": Wholesaler("C", 100, 5, 200, 0.10, 14, "Gain Market Share", "Scrappy")
    }
    
    evaluator = ScenarioEvaluator()

    # --- SCENARIO 1 (SIMPLE) ---
    s1_simple = Scenario1_ReverseAuction(wholesalers)
    logs_s1_s = s1_simple.run(complexity_mode="simple")
    evaluate_s1(s1_simple, logs_s1_s, wholesalers, evaluator, gpt5, "simple")

    # --- SCENARIO 1 (COMPLEX) ---
    s1_complex = Scenario1_ReverseAuction(wholesalers)
    logs_s1_c = s1_complex.run(complexity_mode="complex")
    evaluate_s1(s1_complex, logs_s1_c, wholesalers, evaluator, gpt5, "complex")

    # --- SCENARIO 2 (SIMPLE) ---
    s2_simple = Scenario2_VolumeTrap(wholesalers)
    logs_s2_s = s2_simple.run(complexity_mode="simple")
    evaluate_s2(s2_simple, logs_s2_s, wholesalers, evaluator, gpt5, "simple")

    # --- SCENARIO 2 (COMPLEX) ---
    s2_complex = Scenario2_VolumeTrap(wholesalers)
    logs_s2_c = s2_complex.run(complexity_mode="complex")
    evaluate_s2(s2_complex, logs_s2_c, wholesalers, evaluator, gpt5, "complex")

    # --- SCENARIO 3 ---
    s3 = Scenario3_TimeTravel(wholesalers)
    logs_s3 = s3.run()
    evaluate_s3(s3, logs_s3, wholesalers, evaluator, gpt5)

    # --- SCENARIO 4 ---
    s4 = Scenario4_CostAudit(wholesalers)
    logs_s4 = s4.run()
    evaluate_s4(s4, logs_s4, wholesalers, evaluator, gpt5)

    # --- SCENARIO 5 ---
    s5 = Scenario5_Collusion(wholesalers)
    logs_s5 = s5.run()
    evaluate_s5(s5, logs_s5, wholesalers, evaluator, gpt5)
    
    # Save Results to JSON
    filename = "simulation_results.json"
    with open(filename, "w") as f:
        json.dump(ALL_RESULTS, f, indent=4)
        
    print(f"\n🎉 All Simulations Completed.")
    print(f"💾 Detailed results saved to: {filename}")
