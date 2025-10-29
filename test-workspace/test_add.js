// Import the add function
const fs = require('fs');
const vm = require('vm');

// Read the add.js file and extract the function
const addFileContent = fs.readFileSync('add.js', 'utf8');
// Extract just the function definition (excluding console.log)
const functionCode = addFileContent.split('\n').slice(0, 3).join('\n');

// Create a context to run the function
const context = vm.createContext({});
vm.runInContext(functionCode, context);
const add = context.add;

// Test results tracking
let totalTests = 0;
let passedTests = 0;
let failedTests = [];

// Test helper function
function test(description, input, expected) {
    totalTests++;
    const actual = add(input);
    if (actual === expected) {
        console.log(`✓ ${description}: add(${input}) = ${actual}`);
        passedTests++;
    } else {
        console.log(`✗ ${description}: add(${input}) = ${actual}, expected ${expected}`);
        failedTests.push(`${description}: add(${input}) returned ${actual}, expected ${expected}`);
    }
}

console.log("========================================");
console.log("Testing Updated add() Function - Doubles Input");
console.log("========================================\n");

// Test Suite 1: Positive Numbers
console.log("Test Suite 1: Positive Numbers");
console.log("-------------------------------");
test("Small positive integer", 1, 2);
test("Medium positive integer", 5, 10);
test("Large positive integer", 100, 200);
test("Very large positive integer", 1000, 2000);

console.log("\nTest Suite 2: Negative Numbers");
console.log("-------------------------------");
test("Small negative integer", -1, -2);
test("Medium negative integer", -5, -10);
test("Large negative integer", -100, -200);
test("Very large negative integer", -1000, -2000);

console.log("\nTest Suite 3: Zero");
console.log("-------------------------------");
test("Zero input", 0, 0);

console.log("\nTest Suite 4: Decimal Numbers");
console.log("-------------------------------");
test("Small positive decimal", 0.5, 1);
test("Positive decimal", 2.5, 5);
test("Negative decimal", -2.5, -5);
test("Small negative decimal", -0.5, -1);
test("Pi approximation", 3.14159, 6.28318);

console.log("\nTest Suite 5: Edge Cases");
console.log("-------------------------------");
test("Very small positive", 0.001, 0.002);
test("Very small negative", -0.001, -0.002);
test("Fraction", 1/3, 2/3);
test("Negative fraction", -1/3, -2/3);

console.log("\n========================================");
console.log("TEST RESULTS SUMMARY");
console.log("========================================");
console.log(`Total Tests: ${totalTests}`);
console.log(`Passed: ${passedTests}`);
console.log(`Failed: ${totalTests - passedTests}`);
console.log(`Success Rate: ${(passedTests/totalTests * 100).toFixed(2)}%`);

if (failedTests.length > 0) {
    console.log("\nFailed Tests:");
    failedTests.forEach(failure => console.log(`  - ${failure}`));
} else {
    console.log("\n✅ All tests passed successfully!");
    console.log("The function correctly doubles all input values.");
}

console.log("\n========================================");

// Exit with appropriate code
process.exit(failedTests.length > 0 ? 1 : 0);