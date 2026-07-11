// Source: data/benchmarks/sv-benchmarks/loops-crafted-1/sum_natnum.c

int SIZE = 40000; 

void loopy_449(unsigned int sum) {
  int i;
  
  i = 0, sum =0; 
  while(i< SIZE){ 
      i = i + 1; 
      sum += i;
  }
  {;
//@ assert( sum == ((SIZE *(SIZE+1))/2));
}

  return;
}