// Source: data/benchmarks/sv-benchmarks/loop-industry-pattern/mod3.c
extern int unknown_int(void);

void loopy_356(unsigned int x){
  
  unsigned int y = 1;
  
  while(unknown_int()){
    if(x % 3 == 1){
      x += 2; y = 0;}
    else{
      if(x % 3 == 2){
	x += 1; y = 0;}
      else{
	if(unknown_int()){
	  x += 4; y = 1;}
	else{
	  x += 5; y = 1;}
      }
    }
  }
  if(y == 0)
    {;
//@ assert(x % 3 == 0);
}

  return;
}
