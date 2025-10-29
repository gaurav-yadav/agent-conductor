#!/usr/bin/env node
/**
 * Remove all numeric characters from the provided text.
 * @param {string} text
 * @returns {string}
 */
function deleteNumbers(text) {
  return text.replace(/\d+/g, '');
}

if (require.main === module) {
  const [, , ...args] = process.argv;
  const inputFromArgs = args.length > 0 ? args.join(' ') : null;

  /**
   * Read all data from stdin as a fallback when no CLI argument is provided.
   * @returns {Promise<string>}
   */
  const readFromStdin = () =>
    new Promise((resolve) => {
      let data = '';
      process.stdin.setEncoding('utf8');
      process.stdin.on('data', (chunk) => {
        data += chunk;
      });
      process.stdin.on('end', () => resolve(data));
      process.stdin.resume();
    });

  const handleInput = async () => {
    const rawInput = inputFromArgs ?? (await readFromStdin());
    const normalizedInput = rawInput.trim();

    if (!normalizedInput) {
      console.error('Usage: deleteNumbers <text>\n       echo "text" | deleteNumbers');
      process.exitCode = 1;
      return;
    }

    const result = deleteNumbers(normalizedInput);
    process.stdout.write(result + '\n');
  };

  handleInput().catch((error) => {
    console.error('Failed to delete numbers:', error);
    process.exitCode = 1;
  });
} else {
  module.exports = { deleteNumbers };
}
