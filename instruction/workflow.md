This file is for define my coding workflow. Some steps are manual to don't skip anything and make sure everything continues correct. Please, follow my workflow as shown below and make sure it's proceeding correctly. Ask questions if you need anything.

# PLAN AND CODE
1. My workflow will be using Test Driven Development.
2. First, i will give you requirements and you will create test scenarios shredding to atomic processes.
3. Save test scenarios at infrastructure/test folder with test_scenarios_YYYY_MM_DD_hh_mm name and txt format.
4. I will confirm scenarios manually.
5. Create the technical documentation of request and code according to the standards.md file located in the same folder as this file.

# REVIEW AND TEST
6. Verify the correctness of the code by checking the requests in the `test_scenarios` file within the modified folder. Alert me if you cannot find it.
7. Save test results at test_scenarios folder with name and date as a txt file separately.
8. List required changes to terminal as SRS.
9. Implement changes to code.
10. Verify correctness like 6th step.
11. Repeat between 7th and 10th step until there is no error.
12. Test code quality using alibaba's OpenCodeReview tool.
13. Repeat 11th step.

# PR
14. Add last accepted documentation as an SRS to PR's description.