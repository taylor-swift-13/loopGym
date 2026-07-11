// Source: data/benchmarks/accelerating_invariant_generation/cav/gulv_simp.c
extern int unknown_int(void);

int nondet(){
  int x;
  return x;
}

void loopy_157(void){
int x = 0, y = 0;
while (unknown_int()) {
   if (unknown_int())
     {x = x+1; y = y+100;}
   else if (unknown_int()){
     if (x >= 4)
       {x = x+1; y = y+1;}
   }
 
   x = x; 
}
if (x >= 4 && y <= 2)
  goto ERROR;

return;

{ ERROR: {; 
//@ assert(\false);
}
}
}