const fs = require('fs');

// 快速检查CSV格式
const filePath = '/Users/kelvin/Downloads/獎號/2024/大樂透_2024.csv';
const content = fs.readFileSync(filePath, 'utf-8');
const lines = content.split('\n');

console.log('CSV文件分析:\n');
console.log('第1行(标题):');
console.log(lines[0]);
console.log('\n第2行(第一笔数据):');
console.log(lines[1]);
console.log('\n第3行(第二笔数据):');
console.log(lines[2]);

// 分析第二行
const parts = lines[1].split(',');
console.log(`\n总共 ${parts.length} 列\n`);
console.log('各列内容:');
parts.forEach((part, i) => {
    console.log(`列${i}: ${part.trim()}`);
});
