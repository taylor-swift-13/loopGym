// Source: data/benchmarks/accelerating_invariant_generation/cav/xy10.c
extern int unknown_int(void);

int nondet(){
  int x;
  return x;
}

void loopy_160(int z)
{
  int x = 0;
  int y = 0;
  

  while (unknown_int()){
    x += 10;
    y += 1;
  }

  if (x <= z && y >= z + 1)
    goto ERROR;

return;

  { ERROR: {; 
//@ assert(\false);
}
}
}